import argparse
import json
import time
from portForward import pipeExtention_port_forward, terminate_port_forward, tomcatServer_port_forward, getAuthToken, jobManager_port_forward
from push_datasets import push_executor
from retrievePatienID import get_patient_id
from check_outputjson import check_outputjson_executor, print_test_summary
from tomcatStatusCheck import tomcatModuleStatusChecker
import requests
import subprocess
import os
import threading
import re

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
    # if module_name == "angio":
    #     output_files_to_check = ["output.json", "output_cta.json", "output_lvo.json"]
    # elif module_name == "ncctArtifactDetection":
    #     output_files_to_check = ["artifact_output.json"]
    # else:
    #     output_files_to_check = ["output.json"]

    output_files_to_check = ["output.json"]

    print(f"⏳ Waiting for {', '.join(output_files_to_check)} in: {folder}")
    found_files = set()
    start_json_poll = time.time()

    while time.time() - start_json_poll < 600:  # 10 minutes max
        # -maxdepth 1: Limits the search to the specified directory only (i.e., no recursion into subfolders).
        file_list_cmd = f"find {folder} -maxdepth 1 -type f"
        result = subprocess.run([
            "kubectl", "exec", "-n", NAMESPACE, jomManager_pod,
            "--", "/bin/sh", "-c", file_list_cmd
        ], capture_output=True, text=True)

        files = result.stdout.strip().split("\n") if result.returncode == 0 else []

        for output_file in output_files_to_check:
            # f is the path of files
            for f in files:
                if f.endswith(output_file) and output_file not in found_files:
                    found_files.add(output_file)
                    time.sleep(2)
                    if output_file == "output.json" or output_file== "artifact_output.json":
                        case_id = f"{module_name.upper()}_Case{len(found_files)}"
                        check_outputjson_executor(f, kubeConfigFile, jomManager_pod, NAMESPACE, module_name)

        # if len(found_files) == len(output_files_to_check) or (module_name != "angio" and "output.json" in found_files):
        #     break

        if len(found_files) == len(output_files_to_check):
            break

        time.sleep(5)

    else:
        print(f"⚠️ Timeout: Not all output files found in {folder} within 15 minutes.\n")

def is_task_folder(new_folders):
    valid_folders = set()
    for folder_path in new_folders:
        folder_name = os.path.basename(folder_path)
        if re.fullmatch(r'\d+_\d+', folder_name):
            valid_folders.add(folder_path)
    return valid_folders

def executor(kubeConfigFile, remote_port, NAMESPACE, IP, datasets, parallel_push, kubeconfig_path,
             tomcatServer_local_port, tomcatServer_remote_port, tomcatServer_username, tomcatServer_password,
             siteName, waitPop, statusCheckInterval, push_via):

    base_path = f"/rapid_data/task_data/{siteName}"
    excluded_modules = {"emailSend", "temp_ich", "temp_petn", "DicomSend"}
    poll_duration = 180  # seconds
    poll_interval = 10  # seconds

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
    time.sleep(waitPop)
    start_time = time.time()

    # Polling for new folders
    print(f"⏳ Watching for new task folders (ignoring: {', '.join(excluded_modules)})...\n")
    while time.time() - start_time < poll_duration:
        current_task_folders = list_module_task_paths(kubeConfigFile, NAMESPACE, jomManager_pod, base_path, excluded_modules)
        new_folders = current_task_folders - initial_task_folders
        task_folders = is_task_folder(new_folders)

        if task_folders:
            threads = []
            for folder in task_folders:
                if folder.split('/')[4] != "ncctArtifactDetection":
                    print(f"✅ New task folder detected: {folder}")
                    module_name = folder.split('/')[4]

                    # Start a thread for each folder
                    t = threading.Thread(
                        target=poll_for_output_files,
                        args=(folder, module_name, kubeConfigFile, jomManager_pod, NAMESPACE)
                    )
                    t.start()
                    threads.append(t)
                else:
                    pass
            # Wait for all threads to finish
            for t in threads:
                t.join()

            break  # Exit the outer loop once all threads are done
        time.sleep(poll_interval)
    else:
        print("⌛ No new task folder detected within 2 minutes.")
    # ✅ Final summary
    print_test_summary()


# Add all the dataset paths into a list
def dataset_list(config_data):
    datasets = []
    for key in config_data:
        if key.startswith("dataset_path"):
            datasets.append(config_data[key])
    return datasets