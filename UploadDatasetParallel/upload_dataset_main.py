import argparse
import json
import time
from portForward import pipeExtention_port_forward, terminate_port_forward, tomcatServer_port_forward, getAuthToken, jobManager_port_forward
from push_datasets import push_executor
from retrievePatienID import get_patient_id
from check_outputjson import check_outputjson_main
from tomcatStatusCheck import tomcatModuleStatusChecker
import requests
import subprocess
import os
import threading

def list_module_task_paths(kubeConfigFile, NAMESPACE, jomManager_pod, base_path, excluded_modules):
    cmd = [
        "kubectl", "--kubeconfig", kubeConfigFile, "-n", NAMESPACE,
        "exec", jomManager_pod, "--", "bash", "-c",
        f"cd {base_path} && find . -type d -mindepth 2 -maxdepth 2"
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print("❌ Error fetching folders:", result.stderr)
        return set()

    task_paths = set()
    for line in result.stdout.strip().splitlines():
        parts = line.strip().split("/")
        if len(parts) == 3:  # ./<module>/<task>
            _, module, task = parts
            if module not in excluded_modules:
                task_paths.add(f"{base_path}/{module}/{task}")
    return task_paths

def poll_for_output_files(folder, module_name, kubeConfigFile, jomManager_pod, NAMESPACE):
    output_files_to_check = (
        ["output.json", "output_cta.json", "output_lvo.json"]
        if module_name == "angio"
        else ["output.json"]
    )

    print(f"⏳ Waiting for {', '.join(output_files_to_check)} in: {folder}")
    found_files = set()
    start_json_poll = time.time()

    while time.time() - start_json_poll < 900:  # 15 minutes max
        file_list_cmd = f"find {folder} -type f"
        result = subprocess.run([
            "kubectl", "exec", "-n", NAMESPACE, jomManager_pod,
            "--", "/bin/sh", "-c", file_list_cmd
        ], capture_output=True, text=True)

        files = result.stdout.strip().split("\n") if result.returncode == 0 else []

        for output_file in output_files_to_check:
            for f in files:
                if f.endswith(output_file) and output_file not in found_files:
                    print(f"📄 {output_file} created: {f}")
                    found_files.add(output_file)
                    time.sleep(2)
                    if output_file == "output.json":
                        check_outputjson_main(f, kubeConfigFile, jomManager_pod, NAMESPACE)

        if len(found_files) == len(output_files_to_check) or (
                module_name != "angio" and "output.json" in found_files):
            break

        time.sleep(5)

    else:
        print(f"⚠️ Timeout: Not all output files found in {folder} within 15 minutes.\n")

def executor(kubeConfigFile, remote_port, NAMESPACE, IP, datasets, parallel_push, kubeconfig_path,
             tomcatServer_local_port, tomcatServer_remote_port, tomcatServer_username, tomcatServer_password,
             siteName, waitPop, statusCheckInterval, push_via):

    base_path = f"/rapid_data/task_data/{siteName}"
    excluded_modules = {"emailSend", "temp_ich", "temp_petn"}
    poll_duration = 180  # seconds
    poll_interval = 5  # seconds

    # Set the KUBECONFIG environment variable
    os.environ["KUBECONFIG"] = kubeconfig_path
    # Get the name of the JobManager pod in the specified namespace
    result = subprocess.run(["kubectl", "get", "pods", "-n", NAMESPACE], capture_output=True, text=True, check=True)
    jomManager_pod = None
    for line in result.stdout.split('\n'):
        if "rapid-jobmanager" in line:
            print("rapid-jobmanager exists")
            jomManager_pod = line.split()[0]
            print(jomManager_pod)
            break

    # Snapshot before study push
    print("📸 Taking initial snapshot of task folders...")
    initial_task_folders = list_module_task_paths(kubeConfigFile, NAMESPACE, jomManager_pod, base_path, excluded_modules)
    print(f"Inital task folders : {initial_task_folders}")


    # Push Datasets
    # terminate_port_forward()
    if push_via == "pipe":
        forwarded_port = pipeExtention_port_forward(kubeConfigFile, remote_port, NAMESPACE)
    elif push_via == "jobmanager":
        forwarded_port = jobManager_port_forward(kubeConfigFile, remote_port, NAMESPACE)
    else:
        raise ValueError(f"Invalid push_via value: {push_via}")

    for value in forwarded_port:
        port = value
        print(f"Port forwarded to: {port}")
        push_executor(IP, port, datasets, parallel_push)
        time.sleep(5)
        # Terminating all the processes that has kubectl after Tomcat Port Forward
        # terminate_port_forward()
        break
    print(f"Waiting for {waitPop} seconds so that the studies get populate on Tomcat and start to process...")
    time.sleep(90)
    start_time = time.time()

    # Polling for new folders
    print(f"⏳ Watching for new task folders (ignoring: {', '.join(excluded_modules)})...\n")
    while time.time() - start_time < poll_duration:
        current_task_folders = list_module_task_paths(kubeConfigFile, NAMESPACE, jomManager_pod, base_path, excluded_modules)
        new_folders = current_task_folders - initial_task_folders
        if new_folders:
            threads = []
            for folder in new_folders:
                print(f"✅ New task folder detected: {folder}")
                module_name = folder.split('/')[4]

                # Start a thread for each folder
                t = threading.Thread(
                    target=poll_for_output_files,
                    args=(folder, module_name, kubeConfigFile, jomManager_pod, NAMESPACE)
                )
                t.start()
                threads.append(t)

            # Wait for all threads to finish
            for t in threads:
                t.join()

            break  # Exit the outer loop once all threads are done
        time.sleep(poll_interval)
    else:
        print("⌛ No new task folder detected within 2 minutes.")




    # time.sleep(waitPop)
    # print("<---------------Port Forward TomcatServer to check Live status of the modules--------------->")
    # forwarded_port = tomcatServer_port_forward(kubeconfig_path, tomcatServer_local_port, tomcatServer_remote_port,
    #                                            tomcatServer_username, tomcatServer_password, namespace)
    # for value in forwarded_port:
    #     port = value
    #     print(f"TomcatServer pod Port forwarded to: {port}")
    #     authorization_token = getAuthToken(port, tomcatServer_password, tomcatServer_username)
    #     tomcatModuleStatusChecker(authorization_token, siteName, port, statusCheckInterval)
    #     print("Logging Out the user")
    #     time.sleep(5)
    #     logout_user(port, authorization_token)
    #     print("Sleeping for few seconds before Terminating Tomcat Server Port forward.")
    #     time.sleep(10)
    #
    #     # Terminating all the processes that has kubectl after Tomcat Port Forward
    #     terminate_port_forward()
    # print("Sleeping for few seconds before starting logger.")
    # time.sleep(30)

# def logout_user(port, authorization_token):
#     url = f"https://localhost:{port}/isvapi/service/v1/authenticate/logoutx"
#
#     # Define request headers
#     headers = {
#         'Authorization': str(authorization_token)
#     }
#
#     try:
#         # Send DELETE request with payload as JSON string
#         response = requests.delete(url=url, headers=headers, verify=False)
#         # Check response status code
#         if response.status_code == 200:
#             print(f"Logged out tomcat user successfully.")
#         else:
#             print(f"Error: {response.status_code}")
#             print(response.text)  # Print response body for further debugging if needed
#     except requests.exceptions.RequestException as e:
#         print("Error:", e)

# Add all the dataset paths into a list
def dataset_list(config_data):
    datasets = []
    for key in config_data:
        if key.startswith("dataset_path"):
            datasets.append(config_data[key])
    return datasets

# Create ArgumentParser object
parser = argparse.ArgumentParser(description='Takes argumrnts and push the datasets')
# config_file = '/Users/subhrasis/Documents/Rapid_pythonScripts/Automation_no_global/UploadDatasetParallel/UploadDataset_config.json'
parser.add_argument('global_json_file', help='Path to the global JSON file')

# Parse arguments
args = parser.parse_args()

with open(args.global_json_file, 'r') as f:
    global_data = json.load(f)  # dictionary

datasets = dataset_list(global_data["upload_dataset_params"])

# Printing the Pushed Dataset(s) PatientID into a csv file
get_patient_id(datasets)

executor(global_data["kubeConfigFile"], global_data["upload_dataset_params"]['remote_port'], global_data['namespace'],
         global_data["upload_dataset_params"]['IP'], datasets, global_data["upload_dataset_params"]["parallel_push"],
         global_data["kubeConfigFile"], global_data["tomcatServer_local_port"], global_data["tomcatServer_remote_port"],
         global_data["tomcatServer_username"], global_data["tomcatServer_password"], global_data["siteName"],
         global_data["upload_dataset_params"]['waitPop'], global_data["upload_dataset_params"]['statusCheckInterval'],
         global_data["push_via"])
