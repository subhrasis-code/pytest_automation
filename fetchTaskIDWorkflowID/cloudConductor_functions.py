import json
import subprocess
import time
import requests
import re
import os
from setKubeConfig import set_kubeconfig
from fetch_log_queue import terminate_port_forward


def aws_sso_login():
    # Perform the AWS SSO login once at the start
    print("Please complete the AWS SSO login in your browser.")
    run_command("aws sso login --sso-session isv-sso", shell=True)
    print("AWS SSO login completed.")


def update_kubeconfig(region, profile, cluster_name, alias, cloud_kubeconfig_path):
    # command = f"echo {self.sudo_password} | sudo {export_kube_cmd}" # command = f"echo {sudo_password} | aws eks update-kubeconfig --region {region} --profile {profile} --name {cluster_name} --alias {alias}"
    # command = f"{export_kube_cmd}" # command = f"aws eks update-kubeconfig --region {region} --profile {profile} --name {cluster_name} --alias {alias}"
    # command = f"aws eks update-kubeconfig --region {region} --profile {profile} --name {cluster_name} --alias {alias}"
    set_kubeconfig(cloud_kubeconfig_path)

    command = f"aws eks update-kubeconfig --region {region} --profile {profile} --name {cluster_name}"
    print(f"Executing command: {command}")

    output = run_command(command, capture_output=True, shell=True)
    print(output)


def get_k8s_pods(namespace, cloud_kubeconfig_path, pod_type):
    set_kubeconfig(cloud_kubeconfig_path)
    command = f"kubectl get pods -n {namespace} -o json"
    try:
        output = run_command(command, capture_output=True, shell=True)
        if not output:
            raise Exception("No output from kubectl command")
        pods = json.loads(output)
    except Exception as e:
        print(f"Failed to get pods: {e}")
        return None

    cloud_pod_name = None
    for pod in pods.get('items', []):
        pod_name = pod['metadata']['name']
        if pod_name.startswith(pod_type):
            cloud_pod_name = pod_name
            break

    return cloud_pod_name



def run_command(command, capture_output=False, shell=False):
    try:
        if capture_output:
            print(capture_output)
            result = subprocess.run(command, shell=shell, capture_output=True, text=True, check=True)
            print(result)
            return result.stdout
        else:
            subprocess.run(command, shell=shell, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command '{e.cmd}' failed with return code {e.returncode}")
        print(f"Output: {e.output}")
        print(f"Error: {e.stderr}")
        raise





def port_forward_conductor_pod(pod_name, local_port, remote_port):
    print("Inside port_forward_conductor_pod")
    if pod_name:
        terminate_port_forward()  # Ensure previous port forwarding is terminated
        # command = f"echo {self.sudo_password} | sudo -S kubectl port-forward {pod_name} -n rapid-apps {self.local_port}:{self.remote_port}"
        command = f"kubectl port-forward {pod_name} -n rapid-apps {local_port}:{remote_port}"
        print(f"Port forwarding pod: {pod_name}")

        # Start the port-forward command in a separate process
        process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        # Wait for a moment to ensure port forwarding is established
        time.sleep(5)

        # Check if the process started successfully and read its output
        if process.stdout:
            output = process.stdout.readline().strip()
            print(output)
            process.stdin.flush()

            # Use regex to extract the local port number
            match = re.search(r"Forwarding from \S+:(\d+)", output)
            if match:
                forwarded_port = match.group(1)
                yield forwarded_port
        else:
            print("Error: Unable to start port forwarding process")
            # Keep the script running
            while True:
                time.sleep(1)

def get_cloud_workflowID(corelationID, local_port):
    print(f"\nChecking CorelationId: {corelationID}")
    failed_initCloud_workflowIds = []
    passed_initCloud_workflowIds = []
    url = f"http://localhost:{local_port}/api/workflow/search?start=0&size=15&sort=startTime%3ADESC&freeText={corelationID}&query="
    print(url)

    retries = 10
    for attempt in range(retries):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                for result in data['results']:
                    if result['workflowType'] == 'init_cloud':
                        if result['status'] != 'COMPLETED':
                            failed_initCloud_workflowIds.append(
                                result['workflowId'])  # list of failed_initCloud_workflowIds
                        else:
                            passed_initCloud_workflowIds.append(
                                result['workflowId'])  # # list of passed_initCloud_workflowIds
                # print("Passed init_cloud workflows:", passed_initCloud_workflowIds)
                # print("Failed init_cloud workflows:", failed_initCloud_workflowIds)
                return failed_initCloud_workflowIds, passed_initCloud_workflowIds
            else:
                print(f"{url} is returning {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
            time.sleep(2)  # Wait before retrying


def find_key(json_data, key_to_check):
    if isinstance(json_data, dict):
        # print(f"json_data: {json_data}")
        if key_to_check in json_data:
            print(key_to_check)
            # print(f"Key '{key_to_check}' found with value: {json_data[key_to_check]}")
            return str(json_data[key_to_check])
        for key, value in json_data.items():
            # print(key, value)
            find_key(value, key_to_check)
    elif isinstance(json_data, list):
        for item in json_data:
            find_key(item, key_to_check)
    return False

def get_logs(failed_initCloud_workflowIds, local_port, corelationID, OnPremResultsDir):
    print(
        f"\nGetting the logs for the Failed init_cloud for these workflowIds {failed_initCloud_workflowIds} having corelationId {corelationID}")
    log_detail = ""
    log_detail += f"\nFailure Details for CorrelationID : {corelationID}\n\n"
    for workflowId in failed_initCloud_workflowIds:
        url = f"http://localhost:{local_port}/api/workflow/{workflowId}"
        response = requests.get(url=url)
        if response.status_code == 200:
            dict = response.json()
            for result in range(len(dict['tasks'])):
                status = dict['tasks'][result]['status']
                print(type(dict['tasks'][result]))
                x = json.dumps(dict['tasks'][result])
                y = json.loads(x)
                temp = find_key(y, "correlationId")
                if status != "COMPLETED" and temp == corelationID:
                    log_detail += f"initCloud_workflowId : {workflowId}, OnPremResultsDir : {OnPremResultsDir}"
                    log_detail += f"\nreasonForIncompletion_cloud : {dict['tasks'][result]}\n"
                    log_detail += "\n No Failure Found. There is a known bug, because of which old corelationID's datas get clubed into the current one."
                    # print(result)
                    # print(log_detail)
    return log_detail


# print(get_k8s_pods("rapid-apps", "/Users/subhrasis/Documents/Rapid_pythonScripts/Performance/kubeConfigFiles/admin.alpha-sandpit67f333.kubeconfig", "conductor-server"))