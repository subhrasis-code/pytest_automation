import subprocess
import argparse
import json
import time
from setKubeConfig import set_kubeconfig
from getJobMngrPodName import get_jobmanager_postgres_pod
from copyFromJobMngr import copy_file_from_jobManager
from editFile import edit_file_in_local
from copyToJobMngr import copy_file_to_jobManager
from enableDicom_node import getAuthToken, terminate_port_forward
from portForward import tomcatServer_port_forward
from awsSSO import aws_sso_login
from killing_pod_enable_disable import pod_kill

def get_sites(namespace, postgres_pod_name):
    # Construct the kubectl command to get pods in the specified namespace
    command = f'kubectl exec -n {namespace} {postgres_pod_name} -- psql -U postgres -d rapid -c "SELECT site_name FROM sites" -t'

    # Execute the kubectl command
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    # Check if the command executed successfully
    if result.returncode == 0:
        # Print the output of the command
        sites_list = result.stdout.strip().split('\n')
        return sites_list
    else:
        # Print the error message if the command failed
        print("Error executing the command:")
        print(result.stderr.strip())


def executor(list_of_modules, kubeconfig_path, siteName, namespace, moduleToEnable, emailConfig, tomcatServer_username, tomcatServer_password, tomcatServer_remote_port, tomcatServer_local_port, userEmailList):
    print("************************************ Enabling Module Execution Started ************************************ \n\n")

    print(f"Step 1 <----------------- Setting kubeconfig to {kubeconfig_path} ----------------->\n")
    # Export the kubeconfig file
    set_kubeconfig(kubeconfig_path)

    print("Step 2 <----------------- Fetching Kubernetes podnames ----------------->\n")
    # Return the jobmanager podname and postgress podname
    jobmanager_pod_name, postgres_pod_name, pipeExtention_pod_name = get_jobmanager_postgres_pod(namespace)
    print("Jobmanager pod-name ----> {} \n".format(jobmanager_pod_name))
    print("Postgress pod-name ----> {} \n".format(postgres_pod_name))
    print("Pipe Extention pod-name ----> {} \n".format(pipeExtention_pod_name))
    remote_file_path = f"/opt/rapid4/{siteName}/isv_service_config.xml"

    print("Step 3 <----------------- Copy isv_service file present in jobmanager pod into the local path ----------------->\n")
    # copy isv_service file present in kubernetes pod into the local path.
    local_file_path = copy_file_from_jobManager(remote_file_path, namespace, jobmanager_pod_name)
    time.sleep(0.5)

    print("Step 4 <----------------- Editing isv_service file present in local ----------------->\n")
    print(moduleToEnable)
    # edit the copied isv service file as pert the modules we need to enable and disable.
    edit_file_in_local(local_file_path, moduleToEnable, list_of_modules, emailConfig)
    print(moduleToEnable)
    time.sleep(0.5)

    print("Step 5 <----------------- Copy isv_service file present in local into jobmanager pod ----------------->\n")
    # copy the isv service in local to the job manager(kubernetes pod)
    copy_file_to_jobManager(local_file_path, remote_file_path, namespace, jobmanager_pod_name)
    time.sleep(5)

    print("Step 6 <--------------- Port Forward TomcatServer to Enable Dicom Node and User Email --------------->")
    # Terminating all the processes that has kubectl before Tomcat Port Forward
    terminate_port_forward()
    pod_prefix = "rapid-tomcat"
    pod_kill(pod_prefix, namespace)

    forwarded_port = tomcatServer_port_forward(kubeconfig_path, tomcatServer_local_port, tomcatServer_remote_port,
                                               tomcatServer_username, tomcatServer_password, namespace)
    for value in forwarded_port:
        port = value
        print(f"TomcatServer pod Port forwarded to: {port}")
        getAuthToken(port, tomcatServer_password, tomcatServer_username, moduleToEnable, siteName, userEmailList)
        # Terminating all the processes that has kubectl after Tomcat Port Forward
        terminate_port_forward()
    # pod_kill(pod_prefix, namespace)

    print("************************************ Enabling Module Execution Completed ************************************ \n\n")

# aws_sso_login()

# Create ArgumentParser object
parser = argparse.ArgumentParser(description='Takes arguments and enable/disable modules')
# global_json_file = '/Users/subhrasis/Documents/Rapid_pythonScripts/Automation_no_global/global.json'
parser.add_argument('global_json_file', help='Path to the global JSON file')

# Parse arguments
args = parser.parse_args()

# with open(args.config_json_file, 'r') as f1, open(args.global_json_file, 'r') as f2:
with open(args.global_json_file, 'r') as f2:
    # config_data = json.load(f1)  # dictionary
    global_data = json.load(f2)  # dictionary

executor(global_data["enable_disable_params"]["list_of_modules"], global_data["kubeConfigFile"], global_data["siteName"], global_data["namespace"], global_data["enable_disable_params"]["moduleToEnable"], global_data["enable_disable_params"]["emailConfig"], global_data["tomcatServer_username"], global_data["tomcatServer_password"], global_data["tomcatServer_remote_port"], global_data["tomcatServer_local_port"], global_data["userEmail_list"])
# config_data["emailConfig"] is a dictionary
