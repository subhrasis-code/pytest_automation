import argparse
import json
import subprocess
import psutil
import requests
import time
import os
import csv
from setKubeConfig import set_kubeconfig
from getJobMngrPodName import get_jobmanager_conductorUI_pod
from copyFromJobMngr import copy_workflow_csv_from_jobManager, copy_email_logger_from_jobManager
from runDataExtractor_jobMngr import jobManager_data_extractor, jobManager_email_log_extractor
from portForward import conductorUI_port_forward, tomcatServer_port_forward
from taskStatus_api import status
from filteredLogger import logger_patientId
from fetch_log_queue import getAuthToken, terminate_port_forward
import warnings
from urllib3.exceptions import InsecureRequestWarning
from cloudConductor_functions import aws_sso_login, update_kubeconfig, get_k8s_pods, port_forward_conductor_pod
from cloudConductor_executor import module_checker, runner
from killing_pod_enable_disable import pod_kill
from performance_checker import performance_executor

# Filter out the InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)


def executor(kubeconfig_path, namespace, path_jobManager, conductorUI_remote_port, conductorUI_local_port,
             tomcatServer_remote_port, tomcatServer_local_port, tomcatServer_username, tomcatServer_password, site_name,
             time_traversed, s3bucket_name, s3_server_name, cloud_processing_flag, region, profile, cluster_name, alias,
             cloud_conductorUI_remote_port, cloud_conductorUI_local_port, cloud_kubeconfig_path, onPrem_conductorServer_local_port,
             onPrem_conductorServer_remote_port, onCloud_conductorServer_local_port, onCloud_conductorServer_remote_port,
             performance_duration):
    # Export the kubeconfif file
    set_kubeconfig(kubeconfig_path)
    # Return the jobmanager podname and postgress podname
    print(f"************************************ Fetching Log Execution Started ************************************")
    print("\n")
    print("\n")
    print("Step [1] <---------------Fetching JobManager PodName and ConductorUI PodName-------------->")
    jobmanager_pod_name, conductorUI_pod_name, onPrem_conductorServer_pod_name = get_jobmanager_conductorUI_pod(namespace)
    print("\n")
    print("Jobmanager pod-name ----> {} \n".format(jobmanager_pod_name))
    print("ConductorUI pod-name ----> {} \n".format(conductorUI_pod_name))
    print("OnPrem ConductorServer pod-name ----> {} \n".format(onPrem_conductorServer_pod_name))
    print("\n")

    print(
        "Step [2] <---------------Running DataExtractor py file present in JobManager and saving TaskID and WorkflowID into CSV file------------->")
    jobManager_data_extractor(jobmanager_pod_name, namespace, path_jobManager, time_traversed, site_name)
    time.sleep(1)
    print("\n")

    print(
        "Step [3] <---------------Running Email log extractor py file present in JobManager and saving logs into log file------------->")
    jobManager_email_log_extractor(jobmanager_pod_name, namespace, path_jobManager, site_name, time_traversed)
    time.sleep(1)
    print("\n")


    print("Step [4] <---------------Copying TaskID and WorkflowID CSV file to Local--------------->")
    local_task_workflow_ids_file = copy_workflow_csv_from_jobManager(path_jobManager + "task_workflow_ids.csv",
                                                                     namespace,
                                                                     jobmanager_pod_name)
    time.sleep(1)
    print("\n")

    print("Step [5] <---------------Copying Email Logger log file to Local--------------->")
    local_email_log_file = copy_email_logger_from_jobManager(path_jobManager + "emailLogger.log", namespace,
                                                             jobmanager_pod_name)
    print(local_email_log_file)
    time.sleep(1)
    print("\n")

    print("Step [6] <---------------Port Forward TomcatServer to get Email log Queue and Dicom Log Queue--------------->")
    pod_prefix = "rapid-tomcat"
    pod_kill(pod_prefix, namespace)

    forwarded_port = tomcatServer_port_forward(kubeconfig_path, tomcatServer_local_port, tomcatServer_remote_port,
                                               tomcatServer_username, tomcatServer_password, namespace)
    for value in forwarded_port:
        port = value
        print(f"TomcatServer pod Port forwarded to: {port}")
        getAuthToken(port, tomcatServer_password, tomcatServer_username, site_name)
        print("Termination Tomcat Port Forward process.......")
        terminate_port_forward()
    pod_kill(pod_prefix, namespace)


    print("Step [8] <---------------Port Forward On-Prem ConductorUI--------------->")
    forwarded_port = conductorUI_port_forward(kubeconfig_path, conductorUI_local_port, conductorUI_remote_port,
                                              namespace)
    for value in forwarded_port:
        port = value
        print(f"ConductorUI pod Port forwarded to: {port}")
        print("Step [9] <---------------Task Status Check using API--------------->")
        status(local_task_workflow_ids_file, conductorUI_local_port)
        # print("Step [10] <---------------Filtered logs preparation wrt the patientID(s) pushed in this run--------------->")
        # logger_patientId()
        # print(
        #     f"************************************ Fetching On-Prem Log Execution Completed ************************************")
        time.sleep(5)
        terminate_port_forward()
        break

    print("\nStep [11] <---------------Check whether Cloud Processing is True/False--------------->")
    if cloud_processing_flag == "False":
        print("Cloud Processing Execution is marked as False.")
        print("Checking whether Neuro3D or ANRTN modules are present in the run.")
        check_corelationIds = module_checker(local_task_workflow_ids_file, cloud_processing_flag)

        # Get the directory where the script is located
        script_directory = os.path.dirname(os.path.abspath(__file__))
        current_directory = script_directory
        # print(current_directory)

        # Create the logger directory if it doesn't exist
        logger_directory = os.path.join(current_directory, "logger")
        if not os.path.exists(logger_directory):
            os.makedirs(logger_directory)

        # Define the log file path
        failureCloud_path = os.path.join(logger_directory, "failureCloud.log")

        with open(failureCloud_path, "w") as logFile:
            if check_corelationIds is not None:
                print(f"\nList of CorelationIds for Neuro3D or ANRTN modules : {check_corelationIds}\n")
                update_kubeconfig(region, profile, cluster_name, alias, cloud_kubeconfig_path)
                print("Getting Cloud conductorUI pod name")
                pod_type = "conductor-ui"
                conductor_pod_name = get_k8s_pods(namespace, cloud_kubeconfig_path, pod_type)
                print(f"Cloud conductorUI pod name : {conductor_pod_name}")


                forwarded_port = port_forward_conductor_pod(conductor_pod_name, cloud_conductorUI_local_port,
                                                            cloud_conductorUI_remote_port)
                for value in forwarded_port:
                    port = value
                    print(f"ConductorUI pod Port forwarded to: {port}")
                    time.sleep(5)
                    print("\nStep [12] <---------------Getting logs for Cloud Processing --------------->")
                    failure_logs = runner(conductor_pod_name, cloud_conductorUI_remote_port, cloud_conductorUI_local_port, check_corelationIds, region, profile, cluster_name, alias, namespace)
                    logFile.write(failure_logs)
                    print(
                        f"************************************ Fetching On-Cloud Log Execution Completed ************************************")
                    time.sleep(5)
                    terminate_port_forward()
            else:
                logFile.write("Ran On-prem processing, Neuro3D and ANRTN modules are not present in the run. Not checking Cloud Conductor logs")
                print("Neuro3D and ANRTN modules are not present in the run. Not checking Cloud Conductor logs")
    else:
        print("Cloud Processing Execution is marked as True.")
        print("Expecting all the modules has been processed On-Cloud.")
        check_corelationIds = module_checker(local_task_workflow_ids_file, cloud_processing_flag)

        # Get the directory where the script is located
        script_directory = os.path.dirname(os.path.abspath(__file__))
        current_directory = script_directory
        # print(current_directory)

        # Create the logger directory if it doesn't exist
        logger_directory = os.path.join(current_directory, "logger")
        if not os.path.exists(logger_directory):
            os.makedirs(logger_directory)

        # Define the log file path
        failureCloud_path = os.path.join(logger_directory, "failureCloud.log")

        with open(failureCloud_path, "w") as logFile:
            if check_corelationIds is not None:
                print(f"\nList of CorelationIds : {check_corelationIds}\n")
                update_kubeconfig(region, profile, cluster_name, alias, cloud_kubeconfig_path)
                print("Getting Cloud conductorUI pod name")
                pod_type = "conductor-ui"
                conductor_pod_name = get_k8s_pods(namespace, cloud_kubeconfig_path, pod_type)
                print(f"Cloud conductorUI pod name : {conductor_pod_name}")

                forwarded_port = port_forward_conductor_pod(conductor_pod_name, cloud_conductorUI_local_port,
                                                            cloud_conductorUI_remote_port)

                for value in forwarded_port:
                    port = value
                    print(f"ConductorUI pod Port forwarded to: {port}")
                    time.sleep(5)
                    print("\nStep [12] <---------------Getting logs for Cloud Processing --------------->")
                    failure_logs = runner(conductor_pod_name, cloud_conductorUI_remote_port, cloud_conductorUI_local_port,
                           check_corelationIds, region, profile, cluster_name, alias, namespace)
                    if failure_logs:
                        logFile.write(failure_logs)
                    else:
                        logFile.write("No Error Found in Cloud Logs")
                    print(
                        f"************************************ Fetching On-Cloud Log Execution Completed ************************************")
                    time.sleep(5)
                    terminate_port_forward()
            else:
                logFile.write(
                    "On-Cloud processing, No corelationIds found to get Cloud Conductor logs.")
                print("No corelationIds found to get Cloud Conductor logs.")

    print("\nStep [12] <---------------Check Performance Data--------------->")
    time.sleep(5)
    performance_executor(kubeconfig_path, onPrem_conductorServer_local_port, onPrem_conductorServer_remote_port, cloud_kubeconfig_path,
                         onCloud_conductorServer_local_port, onCloud_conductorServer_remote_port, performance_duration ,namespace)
    time.sleep(10)
    print("End of Performance Logs")

    print(f"************************************ Fetching All the Log Completed ************************************")

aws_sso_login()

# Create ArgumentParser object
parser = argparse.ArgumentParser(
    description='Takes arguments and fetch a CSV file that has all workFlowIDs and TaskIDs')
# config_file = '/Users/subhrasis/Documents/Rapid_pythonScripts/Automation_no_global/fetchTaskIDWorkflowID/fetch_task_workflow_id.json'
parser.add_argument('global_json_file', help='Path to the global JSON file')

# Parse arguments
args = parser.parse_args()

with open(args.global_json_file, 'r') as f:
    global_data = json.load(f)  # dictionary

executor(global_data["kubeConfigFile"], global_data["namespace"], global_data["fetch_logs_params"]["path_jobManager"],
         global_data["fetch_logs_params"]["conductorUI_remote_port"], global_data["fetch_logs_params"]["conductorUI_local_port"],
         global_data["tomcatServer_remote_port"], global_data["tomcatServer_local_port"],
         global_data["tomcatServer_username"], global_data["tomcatServer_password"], global_data["siteName"],
         global_data["fetch_logs_params"]["time_traversed"], global_data["fetch_logs_params"]["s3bucket_name"],
         global_data["fetch_logs_params"]["s3_server_name"], global_data["cloud_processing"], global_data["cloud_conductorUI_params"]["region"],
         global_data["cloud_conductorUI_params"]["profile"], global_data["cloud_conductorUI_params"]["cluster_name"], global_data["cloud_conductorUI_params"]["alias"],
         global_data["cloud_conductorUI_params"]["cloud_conductorUI_remote_port"], global_data["cloud_conductorUI_params"]["cloud_conductorUI_local_port"],
         global_data["cloud_conductorUI_params"]["cloud_kubeconfig_path"], global_data["performance_params"]["onPrem_conductorServer_local_port"],
         global_data["performance_params"]["onPrem_conductorServer_remote_port"], global_data["performance_params"]["onCloud_conductorServer_local_port"],
         global_data["performance_params"]["onCloud_conductorServer_remote_port"], global_data["performance_params"]["duration"])
