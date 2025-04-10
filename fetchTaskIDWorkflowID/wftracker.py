#! /usr/bin/python3
import requests
import argparse
import json
import os
import sys
import csv
import re
import time
import subprocess
from datetime import datetime, timedelta, timezone
from dateutil import tz

def to_date_time_from_epoch(epoch_time):
    utc_datetime = datetime.utcfromtimestamp(epoch_time / 1e3)
    utc_datetime = utc_datetime.replace(tzinfo=timezone.utc)
    return utc_datetime

def to_date_time_utc(datetime_str):
    local_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S.%f")
    return local_datetime.replace(tzinfo=timezone.utc)

def get_workflow_start_event(workflow):
    event = {
        'timestamp': to_date_time_from_epoch(workflow['startTime']),
        'name': 'Workflow {} start'.format(workflow['workflowName'])
    }
    return event

def get_time_delta_seconds(start_time, end_time):
    time_taken = to_date_time_from_epoch(end_time) - to_date_time_from_epoch(start_time)
    return time_taken.total_seconds()

def get_workflow_end_event(workflow):
    event = {
        'timestamp': to_date_time_from_epoch(workflow['endTime']),
        'name': 'Workflow {} end (status={}, time taken = {} seconds)'.format(workflow['workflowName'],
            workflow['status'], get_time_delta_seconds(workflow['startTime'], workflow['endTime']))
    }
    return event

def get_task_name(task):
    if task["referenceTaskName"] != "rapid_cloud_connector_task":
        return task["referenceTaskName"]

    data_type = task["inputData"]["TaskInput"]["rapid_cloud_connector_task"]["DataType"]
    task_name = task["referenceTaskName"]
    if data_type == "SOURCE":
        task_name = "cloud_connector_source"
    if data_type == "RESULTS":
        task_name = "cloud_connector_results"
    return task_name

def get_task_start_event(task, workflow_name):
    task_name = get_task_name(task)
    event = {
        'timestamp': to_date_time_from_epoch(task['startTime']),
        'name': 'Task {} ({}) start'.format(task_name, workflow_name)
    }
    return event

def get_task_end_event(task, workflow_name):
    task_name = get_task_name(task)
    event = {
        'timestamp': to_date_time_from_epoch(task['endTime']),
        'name': 'Task {} ({}) end (status={}, time taken = {} seconds)'.format(task_name,
            workflow_name, task['status'], get_time_delta_seconds(task['startTime'], task['endTime']))
    }
    if task['status'] != 'COMPLETED' and 'reasonForIncompletion' in task.keys():
        event.update({'reasonForIncompletion': task['reasonForIncompletion']})
    return event

def parse_tasks(task_name, tasks, workflow_name):
    task_events = []
    for task in tasks:
        if task_name and task['referenceTaskName'] != task_name:
            continue
        if task["workflowTask"]["type"] not in ["SIMPLE", "SUB_WORKFLOW"]:
            continue
        task_events.append(get_task_start_event(task, workflow_name))
        task_events.append(get_task_end_event(task, workflow_name))
    return task_events

def parse_workflows(task_name, workflows):
    events = []
    for workflow in workflows:
        events.append(get_workflow_start_event(workflow))
        events.append(get_workflow_end_event(workflow))
        task_events = parse_tasks(task_name, workflow['tasks'], workflow['workflowName'])
        events = events + task_events
    return events

def fetch_workflows(url, names, corelation_id):
    workflows = []
    for name in names:
        full_url = url + '/workflow/{}/correlated/{}'.format(name, corelation_id)
        response = requests.get(full_url, params={ 'includeClosed': True, 'includeTasks': True})
        if response.status_code == 200:
            workflows = workflows + response.json()
        else:
            print("Error when fetching workflow {}: {}".format(name, response))
    return workflows

def dump_events(quiet, events):
    if quiet:
        return
    for event in events:
        if 'reasonForIncompletion' in event.keys():
            print("{}: {}, FailureReason: {}".format(event['timestamp'], event['name'],
                                                     event['reasonForIncompletion']))
        else:
            print("{}: {}".format(event['timestamp'], event['name']))

def dump_events_to_folder(results_folder_path, correlation_id, events):
    # If the folder does not exist, create it and add the headers
    events_file_name = "results_summary_"+correlation_id+".txt"
    if results_folder_path != "":
        if not os.path.exists(results_folder_path):
            print("Directory", results_folder_path, "does not exist. Creating it now..")
            os.makedirs(results_folder_path)
        events_file_name = os.path.join(results_folder_path, events_file_name)

    with open(events_file_name, 'a') as events_file:
        for event in events:
            line = "{}: {}".format(event['timestamp'], event['name'])
            if 'reasonForIncompletion' in event.keys():
                line = "{}: {}, FailureReason: {}".format(event['timestamp'], event['name'],
                                                          event['reasonForIncompletion'])
            events_file.write(line + "\n")

def dump_workflows(quiet, task_name, workflows):
    if quiet:
        return
    for workflow in workflows:
        if task_name:
            for task in [task for task in workflow['tasks'] if task['referenceTaskName'] == task_name]:
                print(json.dumps(task, indent=4))
        else:
            print(json.dumps(workflow, indent=4))

def dump_workflows_to_folder(results_folder_path, task_name, workflows):
    if results_folder_path != "":
        if not os.path.exists(results_folder_path):
            print("Directory", results_folder_path, "does not exist. Creating it now..")
            os.makedirs(results_folder_path)
    for workflow in workflows:
        file_name = workflow['workflowName'] + "_" + workflow['workflowId'] + "_" + workflow['correlationId'] + ".txt"
        if results_folder_path != "":
            file_name = os.path.join(results_folder_path, file_name)
        with open(file_name, 'w') as workflow_file:
            if task_name:
                for task in [task for task in workflow['tasks'] if task['referenceTaskName'] == task_name]:
                    json.dump(task, workflow_file, indent=4)
            else:
                json.dump(workflow, workflow_file, indent=4)

def dump_events_to_CSV(results_folder_path, corelation_id, events, module_name):
    summary_file_name = results_folder_path + "/" + "summary.csv"
    header_map = {
            "Corelation ID": "Corelation ID",
            "Module Name": "Module Name",
            "^Workflow process_onprem start": "On-prem Workflow Start",
            "^Workflow process_onprem end": "On-prem Workflow End",
            "^Task cloud_connector_source \(process_cloud_upload\) start": "Source De-id Start",
            "^Task cloud_connector_source \(process_cloud_upload\) end": "Source De-id End",
            "^Task .+_subworkflow \(process_onprem\) start": "On-prem Module Start",
            "^Task .+_subworkflow \(process_onprem\) end": "On-prem Module End",
            "^Task cloud_connector_results \(process_cloud_upload\) start": "Results De-id Start",
            "^Task cloud_connector_results \(process_cloud_upload\) end": "Results De-id End",
            "^Upload Time": "Upload Time (seconds)",
            "^Workflow init_cloud start": "Cloud Workflow Start",
            "^Workflow init_cloud end": "Cloud Workflow End",
            "^Task rapid_rma_dispatcher_task_source \(init_cloud\) start": "RMA Source Dispatcher Start",
            "^Task rapid_rma_dispatcher_task_source \(init_cloud\) end": "RMA Source Dispatcher End",
            "^Task rapid_dicom_dispatcher_task \(init_cloud\) start": "DICOM Source Dispatcher Start",
            "^Task rapid_dicom_dispatcher_task \(init_cloud\) end": "DICOM Source Dispatcher End",
            "^Task .+_subworkflow \(init_cloud\) start": "Cloud Module Start",
            "^Task .+_subworkflow \(init_cloud\) end": "Cloud Module End",
            "^Task rapid_rma_dispatcher_task_v2 \(init_cloud\) start": "RMA Results Dispatcher Start",
            "^Task rapid_rma_dispatcher_task_v2 \(init_cloud\) end": "RMA Results Dispatcher End",
            "^Task rapid_rma_dispatcher_task_v1 \(init_cloud\) start": "RMA Results Dispatcher Start",
            "^Task rapid_rma_dispatcher_task_v1 \(init_cloud\) end": "RMA Results Dispatcher End",
            "^Task rapid_cloud_connector_task_results \(init_cloud\) start": "Cloud Results Dispatch Start",
            "^Task rapid_cloud_connector_task_results \(init_cloud\) end": "Cloud Results Dispatch End",
            "Download Time": "Download Time (seconds)"
            }
    # If file does not exist, create it with necessary headers
    if not os.path.exists(summary_file_name):
        with open(summary_file_name, 'w') as results_file:
            writer = csv.DictWriter(results_file, fieldnames=list(dict.fromkeys(header_map.values())))
            writer.writeheader()

    # Parse events
    row = {}
    for pattern, column in header_map.items():
        matching_events = []
        for event in events:
            if re.match(pattern, event["name"]):
                matching_events.append(event["timestamp"].strftime("%Y-%m-%d %H:%M:%S"))
                row[column] = ",".join(matching_events)

    row["Corelation ID"] = corelation_id
    row["Upload Time (seconds)"] = calculate_upload_time(events)
    row["Download Time (seconds)"] = calculate_download_time(events)
    row["Module Name"] = module_name
    with open(summary_file_name, 'a') as results_file:
        writer = csv.DictWriter(results_file, fieldnames=list(dict.fromkeys(header_map.values())))
        writer.writerow(row)

def calculate_upload_time(events):
    start_pattern = "^Task cloud_connector_source \(process_cloud_upload\) end"
    end_pattern = "^Workflow init_cloud start"
    start_event = None
    end_event = None
    for event in events:
        if re.match(start_pattern, event["name"]):
            start_event = event
            continue
        if re.match(end_pattern, event["name"]):
            end_event = event
            continue
        if start_event and end_event:
            break
    if start_event and end_event:
        return str((end_event["timestamp"] - start_event["timestamp"]).total_seconds())
    return ""

def calculate_download_time(events):
    start_pattern = "^Task rapid_cloud_connector_task_results \(init_cloud\) end"
    end_pattern = "^Workflow process_onprem end"
    start_event = None
    end_event = None
    for event in events:
        if re.match(start_pattern, event["name"]):
            start_event = event
            continue
        if re.match(end_pattern, event["name"]):
            end_event = event
            continue
    if start_event and end_event:
        return str((end_event["timestamp"] - start_event["timestamp"]).total_seconds())
    return ""

def fetch_aws_query_results(log_group, start_time, end_time, query):
    aws_command = "aws logs start-query --log-group-name {} --start-time {} --end-time {} --query-string '{}'".format(
            log_group, start_time, end_time, query)
    results = subprocess.run(aws_command, shell=True, capture_output=True, text=True)
    if results.returncode != 0:
        raise RuntimeError("AWS command to query logs failed:", results.stderr)
    output = json.loads(results.stdout)
    query_id = output["queryId"]
    start_time = time.time()
    time_out=60
    query_results = {}
    query_command = "aws logs get-query-results --query-id {}".format(query_id)
    while True:
        query_results = subprocess.run(query_command, shell=True, capture_output=True, text=True)
        if query_results.returncode != 0:
            raise RuntimeError("AWS command to query id failed:", results.stderr)
        output = json.loads(query_results.stdout)
        if output["status"] == "Failed" or time.time() - start_time >= time_out:
            raise RuntimeError("AWS command to query id failed with status:", output)
        if output["status"] == "Complete":
            return output
        time.sleep(1)
    return {}

def process_cw_event(result):
    event_timestamp = ""
    event_name = ""
    event = {}
    for entry in result:
        if entry["field"] == "@timestamp":
            event_timestamp = to_date_time_utc(entry["value"])
        if entry["field"] == "@message":
            json_entry = json.loads(entry["value"])
            msg_entry = json.loads(json_entry["message"])
            print(msg_entry)
            if "Workflow executed" in json_entry["message"]:
                event_name = "Workflow init_cloud start"
            if "TaskDef" in msg_entry.keys() and "WorkflowName" in msg_entry.keys():
                if "started" in json_entry["message"]:
                    event_name = "Task {} ({}) start".format(msg_entry["TaskDef"],
                                                             msg_entry["WorkflowName"])
                elif "finished" in json_entry["message"]:
                    event_name = "Task {} ({}) end".format(msg_entry["TaskDef"],
                                                           msg_entry["WorkflowName"])
        if event_name and event_timestamp:
            event = {
                'timestamp': event_timestamp,
                'name': event_name
                }
            break
    return event

def parse_events_from_cw_logs(results):
    if len(results) == 0:
        return []
    events = []
    for result in results["results"]:
        event = process_cw_event(result)
        if event:
            events.append(event)
    return events

def fetch_events_from_cloudwatch(args, correlation_id):
    # Check if cloud cluster name is set, if not bail.
    log_group = os.getenv("CLOUD_LOG_GROUP")
    if not log_group:
        return []

    cluster_log_group = "/aws/containerinsights/platform/" + log_group
    end_time = int(time.time())
    start_time = end_time - get_duration_in_seconds(args.duration)
    fields_query = 'fields @timestamp, @message, @logStream, @log'
    timestamp_query = 'sort @timestamp desc'
    skip_kong_query = 'filter @logStream != "kong-proxy"'
    correlation_id_query = 'filter @message like "{}"'.format(correlation_id)
    task_start_end_query = 'filter @message =~ /Task with task id .* started/ or @message =~ /Task with task id .* finished/ or @message like "Workflow executed"'
    limit_query = 'limit 1000'
    query = " | ".join((fields_query, timestamp_query, skip_kong_query, correlation_id_query,
                       task_start_end_query, limit_query))
    results = fetch_aws_query_results(cluster_log_group, start_time, end_time, query)
    return parse_events_from_cw_logs(results)

def track_correlation_id(args, on_prem_conductor_url, cloud_conductor_url, correlation_id):
    corelation_id = correlation_id

    onprem_workflows = []
    if on_prem_conductor_url:
        # Fetch on-prem workflow first.
        onprem_workflows = fetch_workflows(on_prem_conductor_url, [args.on_prem_wf, "process_cloud_upload", "result_processing"], corelation_id)
    cloud_workflows = []
    if cloud_conductor_url:
        cloud_workflows = fetch_workflows(cloud_conductor_url, [args.cloud_wf], corelation_id)

    if args.verbose:
        dump_workflows(args.quiet, args.task_name, onprem_workflows + cloud_workflows)
        if args.dump:
            dump_workflows_to_folder(args.results_folder_path, args.task_name, onprem_workflows + cloud_workflows)
    else:
        events = parse_workflows(args.task_name, onprem_workflows + cloud_workflows)
        if args.cloud_watch and not cloud_workflows:
            events = events + fetch_events_from_cloudwatch(args, correlation_id)
        events = sorted(events, key=lambda e: e['timestamp'])
        dump_events(args.quiet, events)
        if args.dump:
            dump_events_to_folder(args.results_folder_path, corelation_id, events)
            if args.summary:
                module_name = fetch_module_name_from_workflow(onprem_workflows)
                dump_events_to_CSV(args.results_folder_path, corelation_id, events, module_name)

def fetch_module_name_from_workflow(onprem_workflows):
    module_name = ""
    if not onprem_workflows:
        return module_name
    for task in onprem_workflows[0]["tasks"]:
        if task["taskType"] == "workflow_selector":
            module_name = task["inputData"]["TaskInput"]["rapid_workflow_params"]["ModuleName"]
            break
    return module_name

def get_duration_in_minutes(duration):
    duration_value_in_mins = 0
    if 'h' in duration:
        duration_value_in_mins = int(duration.rstip('h')) * 60
    elif 'm' in duration:
        duration_value_in_mins = int(duration.rstrip('m'))
    else:
        raise ValueError("Invalid duration format. Use 'Xh' for hours or 'Xm' for minutes.")
    return duration_value_in_mins

def get_duration_in_seconds(duration):
    duration_value_in_seconds = 0
    if 'h' in duration:
        duration_value_in_seconds = int(duration.rstrip('h')) * 60 * 60
    elif 'm' in duration:
        duration_value_in_seconds = int(duration.rstrip('m')) * 60
    else:
        raise ValueError("Invalid duration format. Use 'Xh' for hours or 'Xm' for minutes.")
    return duration_value_in_seconds

def find_correlation_ids(args, on_prem_conductor_url, root_folder):
    file_paths = []
    duration = args.duration
    failed = args.failed
    # Find files named "workflow_input.json" created in the last specified duration
    duration_value = get_duration_in_minutes(duration)
    threshold_time = datetime.now() - timedelta(minutes=duration_value)

    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file == "workflow_input.json":
                file_path = os.path.join(root, file)
                file_creation_time = datetime.fromtimestamp(os.stat(file_path).st_mtime)
                if file_creation_time > threshold_time:
                    file_paths.append(file_path)

    # Iterate through the list and print the file path and a key from the JSON file
    results = {}
    for file_path in file_paths:
        with open(file_path, 'r') as json_file:
            json_data = json.load(json_file)
            json_key = json_data.get('corelationID', 'Key not found')

        if failed:
            all_workflows = fetch_workflows(on_prem_conductor_url, [args.on_prem_wf, "result_processing", "process_cloud_upload"], json_key)
            for workflow in all_workflows:
                if workflow['status'] != 'COMPLETED':
                    results[file_path] = json_key
                    break
        else:
            results[file_path] = json_key

    return results

def print_correlation_ids(correlation_ids):
    for k, v in correlation_ids.items():
        print(f"Workflow path: {k}, CorrelationID: {v}")
    print("\n")

if __name__ == "__main__":

    help_text = '''
    Pre-requisites for running workflow tracker:
    The following environment variables must be set:

    CONDUCTER_SERVER
    @default: "http://conductor-server.rapid-apps.svc.cluster.local:8080/api"

    This should point to the on-prem instance conductor server. If you are port-forwarding using k8s.
    This can be for example "http://localhost:8080/api". If wftracker is being run from inside the
    jobmanager container, this need not be specified explicitely and it will default to the conductor
    running inside k8s. This can be explicitely set to "" to query only the cloud for example.

    CLOUD_CONDUCTOR_SERVER
    @default: None

    This should point to the cloud instance of conductor. If empty, the tool will skip querying
    cloud conductor. If using port-forwarding, then this can be set to "http://localhost:8081/api"
    for example.

    CLOUD_LOG_GROUP
    @default: None

    This should point to the cloud cluster name in cloud watch if cloud watch logging is desired.
    If empty, no cloud watch logs will be retrieved. This can be set to "alpha-sandpit67f333" for example
    if we need to get metrics from alpha.

    IMPORTANT: If cloud watch based logging is desired, the expectation is that your AWS CLI has been
    configured correctly and you are logged into the right accounts for the tool to be able to fetch
    cloud watch logs. If you are able to run "aws logs.." set of commands, then this tool should
    also work for you.


    Sample use cases:

    1. Fetch a summary of metrics from on-prem cluster only using port-forwarding
    CONDUCTOR_SERVER="http://localhost:8080/api" python3 wftracker.py -c <co-relation-id>

    2. Fetch a summary of metrics from on-prem and cloud cluster using port-forwarding
    CONDUCTOR_SERVER="http://localhost:8080/api" CLOUD_CONDUCTOR_SERVER="http://localhost:8081/api" python3 wftracker.py -c <co-relation-id>

    3. Fetch a summary of metrics from on-prem cluster and cloud watch from alpha:
    CONDUCTOR_SERVER="http://localhost:8080/api" CLOUD_LOG_GROUP="alpha-sandpit67f333" python3 wftracker.py -c <co-relation-id> -cw

    4. Fetch a summary of metrics from cloud watch only (alpha):
    CONDUCTOR_SERVER="" CLOUD_LOG_GROUP="alpha-sandpit67f333" python3 wftracker.py -c <co-relation-id> -cw

    5. Fetch a summary of metrics from cloud conductor server only:
    CONDUCTOR_SERVER="" CLOUD_CONDUCTOR_SERVER="http://localhost:8081/api" python3 wftracker.py -c <co-relation-id>

    6. Fetch metrics for a list of co-relation IDs from a files and dump a summary to "/tmp" and use search window of 1h
    CONDUCTOR_SERVER="http://localhost:8080/api" python3 wftracker.py -cf <co-relation-id-file-list> -d -s -f /tmp/

    7. Scan for all failed workflows in last 2 hours and dump a summary (inside jobmananger only)
    python3 wftracker.py --duration 2h --scan --failed -d -s -f /rapid_data/tmp
    '''
    parser = argparse.ArgumentParser(description=help_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('-c', dest='correlation_id', type=str, help='workflow correlation id')
    parser.add_argument('-cf', dest='correlation_id_file', type=str, help="A file containing one or more correlation IDs")
    parser.add_argument('-f', dest='results_folder_path', type=str, default="", help="Folder path to write results")
    parser.add_argument('-v', dest='verbose', action='store_true', help="Print entire workflow instead of summary")
    parser.add_argument('-cw', dest="cloud_watch", action='store_true', help="Fetch events from cloud watch")
    parser.add_argument('-t', dest='task_name', type=str, help="Print only this task name details")
    parser.add_argument('-d', dest='dump', action='store_true', help="Write results to file system")
    parser.add_argument('-s', dest='summary', action='store_true', help="Write results summary to CSV file")
    parser.add_argument('-q', dest='quiet', action='store_true', help="Do not print anything on stdout")
    parser.add_argument('--scan', dest="scan", action='store_true', help="Scan job manager task directory for all recent workflow runs")
    parser.add_argument('--duration', dest="duration", type=str, default="1h", help="Time interval for scan, default is 1h")
    parser.add_argument('--failed', dest="failed", action='store_true', help="Scan for only failed workflows")
    parser.add_argument('--on-prem-wf', dest="on_prem_wf", type=str, default="process_onprem", help="On-prem workflow name (default process_onprem)")
    parser.add_argument('--cloud-wf', dest="cloud_wf", type=str, default="init_cloud", help="Cloud workflow name (default init_cloud)")
    args = parser.parse_args()
    on_prem_conductor_url = os.getenv("CONDUCTOR_SERVER", default="http://conductor-server.rapid-apps.svc.cluster.local:8080/api")
    cloud_conductor_url = os.getenv("CLOUD_CONDUCTOR_SERVER")

    if args.scan:
        # Scan rapid_data/task_data for all recent runs of workflows
        root_folder = "/rapid_data/task_data"
        correlation_ids = find_correlation_ids(args, on_prem_conductor_url, root_folder)
        if not args.quiet:
            print_correlation_ids(correlation_ids)

        if args.dump:
            for _, correlation_id in correlation_ids.items():
                track_correlation_id(args, on_prem_conductor_url, cloud_conductor_url,
                                     correlation_id)
    else:
        if not args.correlation_id and not args.correlation_id_file:
            print("Please specify a correlation ID either using the -c or -cf argument..")
            sys.exit(1)

        if args.correlation_id_file and not args.dump:
            print("Correlation ID file mode is only supported with -d option")
            sys.exit(1)

        if args.correlation_id:
            # Track individual correlation id
            track_correlation_id(args, on_prem_conductor_url, cloud_conductor_url, args.correlation_id)
            sys.exit(0)

        with open(args.correlation_id_file, 'r') as c_file:
            for line in c_file:
                track_correlation_id(args, on_prem_conductor_url, cloud_conductor_url,
                                     line.strip())