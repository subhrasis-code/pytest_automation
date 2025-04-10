import os
import subprocess

# This method will login to the jobmanager pod and copy isv file from job manager to local machine
def copy_file_from_jobManager(remote_file_path, namespace, jobmanager_pod_name):
    # Get the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = script_directory
    # print(current_directory)
    local_file_path = current_directory+"/local_isv_service_config.xml"
    # Construct the kubectl cp command to copy the file from the pod
    command = f"kubectl cp {namespace}/{jobmanager_pod_name}:{remote_file_path} {local_file_path}"
    # Execute the command
    subprocess.run(command, shell=True, check=True)
    if os.path.exists(local_file_path):
        print("<-----------------Copying isv file from job manager to local machine--------------------->")
        print(f"File {remote_file_path} copied from {jobmanager_pod_name} to {local_file_path} successfully.")
        return local_file_path
    else:
        print(f"File {remote_file_path} did'nt get copy to local.")