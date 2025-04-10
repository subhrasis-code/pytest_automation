import subprocess
import time
import os

root_folder = "/rapid_data/task_data"
output_csv = "task_workflow_ids.csv"

# Email logs related variables

# Email log file name
email_log_file = "rapid_emailsend.log"
# final email logger
emailLogger = "emailLogger.log"

# Dicom Send logs related variables

# Dicom send log file name
dicom_send_log_file = "rapid_dicomsend.log"
# final Dicom send logger
dicomSendLogger = "dicomSendLogger.log"
def jobManager_data_extractor(jobmanager_pod_name, namespace, path_jobManager, time_traversed, site_name, attempt=0):

    print(jobmanager_pod_name)
    print(namespace)
    print(path_jobManager)
    print(time_traversed)
    print(site_name)

    # Maximum number of attempts to copy the file
    max_attempts = 3

    # Get the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = script_directory

    local_data_extractor_py_path = current_directory + "/local_data_extractor.py"
    print("\n")
    print(f"Adding Updated data_extractor.py from {local_data_extractor_py_path} to the JobManager path {path_jobManager}.........")
    # command to copy_data_extractor_from local to_jobManager_command
    command = f"kubectl cp {local_data_extractor_py_path} {namespace}/{jobmanager_pod_name}:{path_jobManager}data_extractor.py"
    subprocess.run(command, shell=True, check=True)
    time.sleep(2)

    print("Checking data_extractor.py script exists in the JobManager Pod.......")
    command = f"kubectl exec -n {namespace} {jobmanager_pod_name} -- stat {path_jobManager}data_extractor.py"

    # With check=True, subprocess.run() raises a CalledProcessError if the subprocess exits with a non-zero status, allowing explicit error handling.
    # Without check=True, the function returns normally regardless of subprocess success, lacking explicit error indication.
    result = subprocess.run(command, shell=True)

    if result.returncode == 0:
        print("data_extractor.py script exists in the JobManager Pod.......Now Running the script")
        # Command to execute the script in the pod
        command = f"kubectl exec -n {namespace} {jobmanager_pod_name} -- /usr/bin/python3 {path_jobManager}data_extractor.py"
        try:
            # {root_folder} {output_csv} {time_traversed} are the arguments that is passed
            subprocess.run(f"{command} {root_folder} {output_csv} {time_traversed} {site_name}", shell=True)
            # Execute the command
            # subprocess.run(command, shell=True, check=True)
            time.sleep(1)
        except subprocess.CalledProcessError as e:
            print(f"Error: Command returned non-zero exit status {e.returncode}")
    else:
        print("data_extractor.py does'nt exist in the pod.")
        if attempt < max_attempts:
            # Increment the attempt counter and call the function again
            jobManager_data_extractor(jobmanager_pod_name, local_data_extractor_py_path, namespace, path_jobManager,
                                      attempt + 1)
        else:
            print(f"Maximum attempts ({max_attempts}) reached. Failed to copy data_extractor.py to the pod.")


def jobManager_email_log_extractor(jobmanager_pod_name, namespace, path_jobManager, site_name,  time_traversed, attempt=0):
    # Email logs root folder
    email_root_folder = f"/rapid_data/task_data/{site_name}/emailSend"
    # Maximum number of attempts to copy the file
    max_attempts = 3

    # Get the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = script_directory

    local_email_log_extractor_py_path = current_directory + "/local_email_log_extractor.py"
    print("\n")
    print(f"Adding Updated email_log_extractor from {local_email_log_extractor_py_path} to the JobManager path {path_jobManager}.........")
    # command to copy_email_log_extractor from local to_jobManager
    command = f"kubectl cp {local_email_log_extractor_py_path} {namespace}/{jobmanager_pod_name}:{path_jobManager}email_log_extractor.py"
    subprocess.run(command, shell=True, check=True)
    time.sleep(2)

    print("Checking email_log_extractor script exists in the JobManager Pod.......")
    command = f"kubectl exec -n {namespace} {jobmanager_pod_name} -- stat {path_jobManager}email_log_extractor.py"

    # With check=True, subprocess.run() raises a CalledProcessError if the subprocess exits with a non-zero status, allowing explicit error handling. Without check=True, the function returns normally regardless of subprocess success, lacking explicit error indication.
    result = subprocess.run(command, shell=True)

    if result.returncode == 0:
        print("email_log_extractor script exists in the JobManager Pod.......Now Running the script")
        # print(print(email_root_folder, emailLogger, time_traversed, path_jobManager, email_log_file))
        # Command to execute the script in the pod
        command = f"kubectl exec -n {namespace} {jobmanager_pod_name} -- /usr/bin/python3 {path_jobManager}email_log_extractor.py"
        try:
            # {root_folder} {output_csv} {time_traversed} are the arguments that is passed
            subprocess.run(f"{command} {email_root_folder} {emailLogger} {time_traversed} {path_jobManager} {email_log_file}", shell=True)
            # Execute the command
            # subprocess.run(command, shell=True, check=True)
            time.sleep(1)
        except subprocess.CalledProcessError as e:
            print(f"Error: Command returned non-zero exit status {e.returncode}")
    else:
        print("email_log_extractor does'nt exist in the pod.")
        if attempt < max_attempts:
            # Increment the attempt counter and call the function again
            jobManager_email_log_extractor(jobmanager_pod_name, local_email_log_extractor_py_path, namespace, path_jobManager,
                                      attempt + 1)
        else:
            print(f"Maximum attempts ({max_attempts}) reached. Failed to copy email_log_extractor to the pod.")