import argparse
import json
import time
import subprocess
import os
import threading
import re
import logging
import sys
import requests

from portForward import pipeExtention_port_forward, conductorUI_port_forward, terminate_port_forward, tomcatServer_port_forward, getAuthToken, jobManager_port_forward
from push_datasets import push_executor
# from retrievePatienID import get_patient_id
from check_outputjson import check_outputjson_executor, print_test_summary
import modify_dcm

# from tomcatStatusCheck import tomcatModuleStatusChecker
# import requests

# Logger setup
logger = logging.getLogger("upload_dataset_main")
logger.setLevel(logging.DEBUG)  # Capture all logs DEBUG and above

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def list_module_task_paths(kubeConfigFile, NAMESPACE, jobManager_pod, base_path, excluded_modules):
    cmd = [
        "kubectl", "--kubeconfig", kubeConfigFile, "-n", NAMESPACE,
        "exec", jobManager_pod, "--", "bash", "-c",
        f"cd {base_path} && find . -type d -mindepth 2 -maxdepth 2"
    ]
    logger.debug(f"Running command to fetch task folders: {' '.join(cmd)}")
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"Error fetching folders: {result.stderr.strip()}")
        return set()

    task_paths = set()
    for line in result.stdout.strip().splitlines():
        parts = line.strip().split("/")
        if len(parts) == 3:  # ./<module>/<task>
            _, module, task = parts
            if module not in excluded_modules:
                task_paths.add(f"{base_path}/{module}/{task}")
    logger.debug(f"Found task folders (excluding {excluded_modules}): {task_paths}\n")

    # if clear_site:
    #     print(f"::::::: {clear_site} :::::::")
    #     logger.info(f"Clearing all non-excluded folders (emailSend, temp_ich, temp_petn, DicomSend) in: {base_path}")
    #     delete_tasks(jobManager_pod, NAMESPACE, base_path, excluded_modules)
    #     task_paths = list_module_task_paths(kubeConfigFile, NAMESPACE, jobManager_pod, base_path, excluded_modules, clear_site=False)
    #
    return task_paths


def delete_tasks(jobManager_pod, NAMESPACE, base_path, excluded_modules):
    all_modules = []
    # Step 1: List all folders under base path inside pod
    list_cmd = [
        "kubectl", "exec", jobManager_pod, "-n", NAMESPACE, "--",
        "bash", "-c", f"ls -1 {base_path}"
    ]
    try:
        result = subprocess.run(list_cmd, capture_output=True, text=True, check=True)
        # Split lines, strip whitespace, and filter out empty strings
        all_modules = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
        if not all_modules:
            logger.debug("⚠️ No modules found under the base path.")
            # continue without exiting

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Failed to list folders: {e.stderr}")
        return


    # Step 2: Determine which folders to delete
    to_delete = [module for module in all_modules if module not in excluded_modules]

    # Step 3: Delete each folder
    for module in to_delete:
        full_path = f"{base_path}/{module}"
        delete_cmd = [
            "kubectl", "exec", jobManager_pod, "-n", NAMESPACE, "--",
            "rm", "-rf", full_path
        ]
        try:
            subprocess.run(delete_cmd, check=True)
            logger.info(f"✅ Deleted: {full_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Failed to delete {full_path}: {e.stderr}")

def check_conductor_workflow_status(port, c_id, wf_id, environment, folder, module_name, max_retries=3):
    """
    Check the status of a workflow in Conductor UI by searching for its ID.
    Includes retry mechanism with delay.
    
    Args:
        port (str): Port number where conductor UI is running
        workflow_id (str): Workflow ID or correlation ID to search for
        environment (str): Environment environment (e.g., 'onprem')
        max_retries (int): Maximum number of retry attempts
    
    Returns:
        bool: True if workflow was found and API call successful, False otherwise
    """
    url = f"http://localhost:{port}/api/workflow/search?start=0&size=15&sort=startTime%3ADESC&freeText={c_id}&query="
    logger.info("\n\n")
    logger.info(f"FolderName : {folder}, ModuleName : {module_name}, WorkflowID : {wf_id}, CorrelationID : {c_id}")
    logger.info(f"Checking workflow status in {environment} conductor UI: {url}")
    
    for attempt in range(max_retries):
        try:
            # Add increasing delay between retries
            time.sleep(2 * (attempt + 1))
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                workflow_data = response.json()
                logger.info(f"✅ Successfully fetched workflow definitions from {environment} Conductor UI for correlation ID: {c_id}")
                logger.debug("Workflow Definitions:\n" + json.dumps(workflow_data, indent=2, sort_keys=True))
                return True
            else:
                logger.error(f"❌ Failed to fetch workflow definitions: {response.status_code} - {response.text}")
        except requests.RequestException as e:
            if attempt < max_retries - 1:
                logger.warning(f"⚠️ Attempt {attempt + 1} failed, retrying... Error: {str(e)}")
            else:
                logger.error(f"❌ Error connecting to Conductor UI after {max_retries} attempts: {str(e)}")
    return False

def poll_for_output_files(folder, module_name, kubeConfigFile, jobManager_pod, NAMESPACE):
    has_output_json = None
    has_results = None
    has_workflow_input_json = None
    start_time = time.time()
    timeout = 900  # 15 minutes

    logger.info(f"Starting to monitor: {folder}")

    def setup_conductor_ui():
        environment = "onprem"
        try:
            onprem_cui_port = list(conductorUI_port_forward(kubeConfigFile, str(5000), NAMESPACE, str(5000), environment))
            logger.info(f"Port forwarded ports: {onprem_cui_port}")

            # Only check conductor status if we have a correlation ID
            if onprem_cui_port and onprem_cui_port[0]:
                port = onprem_cui_port[0]
                if c_id:  # Only check status if we have a correlation ID
                    logger.info(f"Port forwarded {environment} conductorUI to: {port}")
                    check_conductor_workflow_status(port, c_id, wf_id, environment, folder, module_name)
                else:
                    logger.warning("No correlation ID available, skipping conductor status check")
                return True
            else:
                logger.error("Failed to get conductor UI port")
                return False
        except Exception as e:
            logger.error(f"Error in port forwarding: {str(e)}")
            return False

    def extract_workflow_input_json():
        # Read workflowID and correlationID from workflow_input.json
        cmd_read_json = f"cat {folder}/workflow_input.json"
        result_json = subprocess.run(
            ["kubectl", "exec", "-n", NAMESPACE, jobManager_pod, "--", "/bin/sh", "-c", cmd_read_json],
            capture_output=True, text=True)
        try:
            workflow_data = json.loads(result_json.stdout)
            workflow_id = workflow_data.get('workflowID')
            correlation_id = workflow_data.get('corelationID')
            logger.info(f"Found workflowID: {workflow_id}, corelationID: {correlation_id}")
            return workflow_id, correlation_id
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse workflow_input.json: {e}")
            return None, None

    # Initialize workflow IDs as None
    wf_id = None
    c_id = None

    while time.time() - start_time < timeout:
        # Check if the task folder itself exists
        cmd = f"test -d {folder} && echo 'Found'"
        result = subprocess.run(["kubectl", "exec", "-n", NAMESPACE, jobManager_pod, "--", "/bin/sh", "-c", cmd],
                              capture_output=True, text=True)
        if 'Found' not in result.stdout:
            logger.error(f"Task folder {folder} does not exist!")
            setup_conductor_ui()  # Setup conductor UI even if folder doesn't exist
            return False

        # Check for files
        cmd_json = f"test -f {folder}/output.json && echo 'Found'"
        cmd_results = f"test -d {folder}/results && echo 'Found'"
        cmd_workflow_input= f"test -f {folder}/workflow_input.json && echo 'Found'"

        result_json = subprocess.run(["kubectl", "exec", "-n", NAMESPACE, jobManager_pod, "--", "/bin/sh", "-c", cmd_json],
                                   capture_output=True, text=True)
        result_results = subprocess.run(["kubectl", "exec", "-n", NAMESPACE, jobManager_pod, "--", "/bin/sh", "-c", cmd_results],
                                      capture_output=True, text=True)
        result_workflow_input = subprocess.run(["kubectl", "exec", "-n", NAMESPACE, jobManager_pod, "--", "/bin/sh", "-c", cmd_workflow_input],
                                                capture_output=True, text=True)

        has_output_json = 'Found' in result_json.stdout
        has_results = 'Found' in result_results.stdout
        has_workflow_input_json = 'Found' in result_workflow_input.stdout


        # If we have workflow input, check other conditions
        if has_workflow_input_json:
            # Read workflowID and correlationID from workflow_input.json
            wf_id, c_id = extract_workflow_input_json()
            # Happy path - all files present
            if has_output_json and has_results:
                logger.info(f"✅ Found output.json, results folder and workflow_input.json in {folder}")
                try:
                    check_outputjson_executor(f"{folder}/output.json", kubeConfigFile, jobManager_pod, NAMESPACE,
                                           module_name, f"{folder}/results")
                    logger.info(f"✅ Successfully processed output.json for {module_name}")
                    setup_conductor_ui()  # Setup conductor UI after successful processing
                    return True
                except Exception as e:
                    logger.error(f"❌ Error processing output.json for {module_name}: {str(e)}")
                    setup_conductor_ui()  # Setup conductor UI even if processing failed
                    return False
            # Partial files present - continue monitoring
            elif has_output_json or has_results:
                logger.warning(f"⚠️ Missing either output.json or results folder in {folder}. Checking again...")
                # Continue monitoring by not returning here
            # Neither file present - continue monitoring
            else:
                logger.warning(f"⚠️ Neither output.json nor results folder found in {folder}. Checking again...")
                # Continue monitoring by not returning here
        else:
            logger.warning(f"⚠️ Waiting for workflow_input.json to be created in {folder}")
            # Continue monitoring by not returning here

        time.sleep(10)  # Check every 10 seconds

    # If we reach here, we've timed out
    elapsed = time.time() - start_time
    logger.error(f"❌ Timeout after {elapsed:.0f} seconds waiting for files in {folder}")
    logger.error(f"Final state for {module_name}:")
    if not has_output_json and not has_results:
        logger.error(f"❌ Neither output.json nor results folder found in {folder}")
    elif has_output_json and not has_results:
        logger.error(f"❌ Found output.json but still waiting for results folder in {folder}")
    elif not has_output_json and has_results:
        logger.error(f"❌ Found results folder but still waiting for output.json in {folder}")

    # Check for any errors in rapid.log
    cmd = f"test -f {folder}/application/logs/rapid.log && grep -i error {folder}/application/logs/rapid.log"
    result = subprocess.run(["kubectl", "exec", "-n", NAMESPACE, jobManager_pod, "--", "/bin/sh", "-c", cmd],
                          capture_output=True, text=True)
    if result.stdout and 'error' in result.stdout.lower():
        logger.error(f"Found errors in {module_name} rapid.log:")
        logger.error(result.stdout)

    # Setup conductor UI after timeout
    setup_conductor_ui()
    return False
def is_task_folder(new_folders):
    valid_folders = set()
    for folder_path in new_folders:
        folder_name = os.path.basename(folder_path)
        if re.fullmatch(r'\d+_\d+', folder_name):
            valid_folders.add(folder_path)
    logger.debug(f"Filtered valid task folders: {valid_folders}")
    return valid_folders


def get_kube_resource(resource_type, NAMESPACE):
    logger.debug(f"Getting Kubernetes resources: {resource_type} in namespace {NAMESPACE}")
    result = subprocess.run(["kubectl", "get", resource_type, "-n", NAMESPACE], capture_output=True, text=True, check=True)
    return result


def get_service_details(service_name, NAMESPACE, result):
    lines = result.stdout.strip().split('\n')
    headers = lines[0].split()
    type_idx = headers.index("TYPE")
    external_ip_idx = headers.index("EXTERNAL-IP")
    name_idx = headers.index("NAME")

    for line in lines[1:]:
        columns = line.split()
        if columns[name_idx] == service_name:
            service_type = columns[type_idx]
            external_ip = columns[external_ip_idx]
            if service_type == "LoadBalancer":
                logger.info(f"Service {service_name} is LoadBalancer with external IP {external_ip}")
                return service_name, service_type, external_ip
            else:
                logger.info(f"Service {service_name} type is {service_type} with no external IP")
                return service_name, service_type, None

    logger.warning(f"Service {service_name} not found in namespace {NAMESPACE}")
    return None, None, None

def run_dcm_modify(datasets):
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # script_path = os.path.join(script_dir, "py_script_to_modify_dcm.sh")
    script_path = os.path.join(script_dir, "modify_dcm.py")

    for dataset_path in datasets:
        logger.info(f"Modifying dcmfiles for : {dataset_path}")
        issuer_id = "aos2"
        # Build the command
        # command = ["sh", script_path , dataset_path, issuer_id]

        command = [
                    "python3",
                    script_path,
                    "--path", dataset_path,
                    "--issuer", issuer_id,
                    "--studyDate", "0",
                    "--studyTime", "0"
                ]


        # Run the command
        try:
            subprocess.run(command, check=True)
            print("✅ modify_dcm.py executed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error running modify_dcm.py: {e}")

# run_dcm_modify(["/Users/zinnov/Documents/Auto_modules_6_2/test_pulse_data/dataset_bundles/MiniRegression/RVLV"])

# def get_postgres_study(postgres_pod, siteName, NAMESPACE):
#
#     logger.debug(f"Getting the study table for {siteName} present in {postgres_pod}")
#     study_table = siteName + "_study"
#     series_tabel = siteName + "_series"
#     logger.info(f"Study Table name : {study_table}")
#
#     try:
#         get_query = f"SELECT * FROM {study_table};"
#         get_result = subprocess.run([
#         "kubectl", "exec", postgres_pod, "-n", NAMESPACE, "--",
#         "psql", "-U", "postgres", "-d", "rapid", "-c", get_query], capture_output=True, text=True, check=True)
#         print("✅ Query Output:")
#         print(get_result.stdout)
#
#     except subprocess.CalledProcessError as e:
#         print(f"❌ Error running kubectl/psql: {e.stderr}")
#
#     try:
#         truncate_query = f"TRUNCATE TABLE {study_table}, {series_tabel};"
#         truncate_result = subprocess.run([
#         "kubectl", "exec", postgres_pod, "-n", NAMESPACE, "--",
#         "psql", "-U", "postgres", "-d", "rapid", "-c", truncate_query], capture_output=True, text=True, check=True)
#         print("✅ Table cleared:")
#         print(truncate_result.stdout)
#
#     except subprocess.CalledProcessError as e:
#         print(f"❌ Error running kubectl/psql: {e.stderr}")





def executor(kubeConfigFile, remote_port, NAMESPACE, IP, datasets, parallel_push, kubeconfig_path,
             tomcatServer_local_port, tomcatServer_remote_port, tomcatServer_username, tomcatServer_password,
             siteName, waitPop, statusCheckInterval, push_via, use_external_ip, multi_associations, multi_asso_batch_count,
             multi_asso_batch_delay, assert_after_push):

    base_path = f"/rapid_data/task_data/{siteName}"
    excluded_modules = {"emailSend", "temp_ich", "temp_petn", "DicomSend"}
    poll_duration = 180  # seconds
    poll_interval = 10  # seconds

    # Set the KUBECONFIG environment variable
    os.environ["KUBECONFIG"] = kubeconfig_path
    logger.info(f"KUBECONFIG set to {kubeconfig_path}")

    jobManager_pod = ""
    pipe_xtention_pod = ""
    postgres_pod = ""
    result = get_kube_resource("pods", NAMESPACE)
    for line in result.stdout.strip().split('\n'):
        columns = line.split()
        if len(columns) < 3 or columns[0] == "NAME": # skip header
            continue

        pod_name = columns[0]
        pod_status = columns[2]

        if "rapid-jobmanager" in pod_name and not jobManager_pod:
            jobManager_pod = pod_name
            logger.info(f"Found jobManager pod: {jobManager_pod}")
        if "rapid-pipe" in pod_name and not pipe_xtention_pod:
            pipe_xtention_pod = pod_name
            logger.info(f"Found pipe extension pod: {pipe_xtention_pod}")
        if "postgres-" in pod_name and pod_status=="Running" and not postgres_pod:
            postgres_pod = pod_name
            logger.info(f"Found postgres pod: {postgres_pod}")
        if "conductor-ui" in pod_name and pod_status=="Running":
            onprem_conductor_ui_pod = pod_name
            logger.info(f"Found conductor UI pod: {onprem_conductor_ui_pod}")
        if jobManager_pod and pipe_xtention_pod:
            break

    # if postgres_pod :
    #     get_postgres_study(postgres_pod, siteName, NAMESPACE)
    # else:
    #     logger.error("No postgres pod found")

    logger.info("Taking initial snapshot of task folders...")
    initial_task_folders = list_module_task_paths(kubeConfigFile, NAMESPACE, jobManager_pod, base_path, excluded_modules)
    logger.info(f"Initial task folders: {initial_task_folders}")

    def call_push_exec(forwarded_port):
        for value in forwarded_port:
            port = value
            logger.info(f"Port forwarded to: {port}")
            series_descriptions_list, series_instance_uids_list, study_instance_uids_list, patient_names_list = push_executor(IP, port, datasets, parallel_push, multi_associations, multi_asso_batch_count, multi_asso_batch_delay)
            time.sleep(5)
            # terminate_port_forward()
            # break
            return series_descriptions_list, series_instance_uids_list, study_instance_uids_list, patient_names_list

    # Push Datasets
    result = get_kube_resource("services", NAMESPACE)
    service_map = {
        "pipe": ("orchestra-ext-service", pipeExtention_port_forward),
        "jobmanager": ("rapid-jobmanager", jobManager_port_forward)
    }

    if push_via not in service_map:
        logger.error(f"Invalid push_via value: {push_via}")
        raise ValueError(f"Invalid push_via value: {push_via}")

    service_name, port_forward_func = service_map[push_via]

    if use_external_ip == "True":
        svc_name, service_type, external_ip = get_service_details("orchestra-ext-service", NAMESPACE, result)
        logger.info(f"service_name: {service_name}")
        logger.info(f"service_type: {service_type}")
        logger.info(f"external_ip: {external_ip}")

        if not external_ip:
            logger.info(f"No external IP present, pushing files via Port Forwarding ({push_via}).")
            forwarded_port = port_forward_func(kubeConfigFile, remote_port, NAMESPACE)
            series_descriptions_list, series_instance_uids_list, study_instance_uids_list, patient_names_list = call_push_exec(forwarded_port)
        else:
            logger.info(f"Pushing files directly to external IP: {external_ip}")
            series_descriptions_list, series_instance_uids_list, study_instance_uids_list, patient_names_list = push_executor(external_ip, remote_port, datasets, parallel_push, multi_associations, multi_asso_batch_count, multi_asso_batch_delay)
    else:
        logger.info(f"Pushing files via Port Forwarding ({push_via})")
        forwarded_port = port_forward_func(kubeConfigFile, remote_port, NAMESPACE)
        series_descriptions_list, series_instance_uids_list, study_instance_uids_list, patient_names_list = call_push_exec(forwarded_port)

    logger.info("Dataset pushed successfully")
    logger.info(
        f"\n🧠📂 ===== Source Datasets DICOM Info =====\n"
        f"🔸 PatientNames       : {patient_names_list}\n"
        f"🔸 StudyInstanceUIDs  : {study_instance_uids_list}\n"
        f"🔸 SeriesInstanceUIDs : {series_instance_uids_list}\n"
        f"🔸 SeriesDescriptions : {series_descriptions_list}\n"
    )
    logger.info(f"Waiting for {waitPop} seconds so that the studies get populated on Tomcat and start to process...")
    time.sleep(waitPop)

    if assert_after_push == "True":
        start_time = time.time()
        logger.info(f"Watching for new task folders (ignoring: {', '.join(excluded_modules)})...\n")
        while time.time() - start_time < poll_duration:
            current_task_folders = list_module_task_paths(kubeConfigFile, NAMESPACE, jobManager_pod, base_path, excluded_modules)
            new_folders = current_task_folders - initial_task_folders
            task_folders = is_task_folder(new_folders)

            if task_folders:
                threads = []
                for folder in task_folders:
                    if folder.split('/')[4] != "ncctArtifactDetection":
                        logger.info(f"New task folder detected: {folder}")
                        module_name = folder.split('/')[4]

                        t = threading.Thread(
                            target=poll_for_output_files,
                            args=(folder, module_name, kubeConfigFile, jobManager_pod, NAMESPACE)
                        )
                        t.start()
                        threads.append(t)
                    else:
                        logger.debug(f"Skipping folder (ncctArtifactDetection): {folder}")
                for t in threads:
                    t.join()

                break
            time.sleep(poll_interval)
        else:
            logger.warning("No new task folder detected within 3 minutes.")
        logger.info("Final test summary:")
        print_test_summary(series_descriptions_list, series_instance_uids_list, study_instance_uids_list, patient_names_list)
    else:
        logger.info("assert_after_push set to False, skipping assert_after_push step.")

    run_dcm_modify(datasets)

def dataset_list(config_data):
    datasets = []
    for key in config_data:
        if key.startswith("dataset_path"):
            datasets = config_data[key].split(",")
    logger.debug(f"Dataset list created: {datasets}")
    return datasets



# poll_for_output_files("/rapid_data/task_data/site1/Hyperdensity/2833_94176", "Hyperdensity", "/Users/zinnov/Documents/Auto_modules_6_2/test_pulse_data/kubeconfigs/admin.ceph-test-phoenix.kubeconfig", "rapid-jobmanager-786c77c6c7-zdzmn", "rapid-apps")
