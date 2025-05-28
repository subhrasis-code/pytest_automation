import argparse
import json
import time
import subprocess
import os
import threading
import re
import logging
import sys

from portForward import pipeExtention_port_forward, terminate_port_forward, tomcatServer_port_forward, getAuthToken, jobManager_port_forward
from push_datasets import push_executor
# from retrievePatienID import get_patient_id
from check_outputjson import check_outputjson_executor, print_test_summary

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
    return task_paths


def poll_for_output_files(folder, module_name, kubeConfigFile, jobManager_pod, NAMESPACE):
    output_files_to_check = ["output.json"]

    logger.info(f"Waiting for {', '.join(output_files_to_check)} in: {folder}")
    found_files = set()
    start_json_poll = time.time()

    while time.time() - start_json_poll < 900:  # 10 minutes max
        file_list_cmd = f"find {folder} -maxdepth 1 -type f"
        result = subprocess.run([
            "kubectl", "exec", "-n", NAMESPACE, jobManager_pod,
            "--", "/bin/sh", "-c", file_list_cmd
        ], capture_output=True, text=True)

        files = result.stdout.strip().split("\n") if result.returncode == 0 else []
        # logger.debug(f"Files found in {folder}: {files}")

        for output_file in output_files_to_check:
            for f in files:
                if f.endswith(output_file) and output_file not in found_files:
                    found_files.add(output_file)
                    time.sleep(2)
                    if output_file in {"output.json", "artifact_output.json"}:
                        case_id = f"{module_name.upper()}_Case{len(found_files)}"
                        logger.info(f"Detected {output_file} for {module_name}, running output json executor for {case_id}")
                        check_outputjson_executor(f, kubeConfigFile, jobManager_pod, NAMESPACE, module_name)

        if len(found_files) == len(output_files_to_check):
            logger.info(f"All expected output files found in {folder}")
            break

        time.sleep(5)
    else:
        logger.warning(f"Timeout: Not all output files found in {folder} within 10 minutes.")


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
    result = get_kube_resource("pods", NAMESPACE)
    for line in result.stdout.strip().split('\n'):
        if "rapid-jobmanager" in line and not jobManager_pod:
            jobManager_pod = line.split()[0]
            logger.info(f"Found jobManager pod: {jobManager_pod}")
        if "rapid-pipe" in line and not pipe_xtention_pod:
            pipe_xtention_pod = line.split()[0]
            logger.info(f"Found pipe extension pod: {pipe_xtention_pod}")
        if jobManager_pod and pipe_xtention_pod:
            break

    logger.info("Taking initial snapshot of task folders...")
    initial_task_folders = list_module_task_paths(kubeConfigFile, NAMESPACE, jobManager_pod, base_path, excluded_modules)
    # logger.info(f"Initial task folders: {initial_task_folders}")

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


def dataset_list(config_data):
    datasets = []
    for key in config_data:
        if key.startswith("dataset_path"):
            datasets = config_data[key].split(",")
    logger.debug(f"Dataset list created: {datasets}")
    return datasets


# def dataset_list(config_data):
#     datasets = []
#     for key in config_data:
#         if key.startswith("dataset_path"):
#             datasets.append(config_data[key])
#     logger.debug(f"Dataset list created: {datasets}")
#     return datasets
