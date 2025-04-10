import os
import csv
import subprocess


# This method will login to the jobmanager pod and copy task_workflow_ids.csv file from job manager to local machine
def copy_workflow_csv_from_jobManager(remote_file_path, namespace, jobmanager_pod_name):
    corelation_ids = [] # corelation_ids is required for Performance related test

    # Construct the kubectl exec command to check if the file exists in the pod
    command_check_existence = f"kubectl exec -n {namespace} {jobmanager_pod_name} -- stat {remote_file_path}"
    # Execute the command to check if the file exists
    try:
        subprocess.run(command_check_existence, shell=True, check=True)
        print(f"File {remote_file_path} exists in {jobmanager_pod_name}. Proceeding with copying...")

        # Get the directory where the script is located
        script_directory = os.path.dirname(os.path.abspath(__file__))
        current_directory = script_directory

        # Create the logger directory if it doesn't exist
        logger_directory = os.path.join(current_directory, "logger")
        if not os.path.exists(logger_directory):
            os.makedirs(logger_directory)

        # Define the log file path
        local_task_workflow_ids_file = os.path.join(logger_directory, "local_task_workflow_ids.csv")
        # c_ids_file will contain only the correlation ids,the file will be passed as argumemnt into performance testing
        c_ids_file = os.path.join(logger_directory, "c_ids")

        # Construct the kubectl cp command to copy the file from the pod
        command_copy_file = f"kubectl cp {namespace}/{jobmanager_pod_name}:{remote_file_path} {local_task_workflow_ids_file}"
        # Execute the command to copy the file
        subprocess.run(command_copy_file, shell=True, check=True)
        if os.path.exists(local_task_workflow_ids_file):
            print(
                "<-----------------Copying task_workflow_ids.csv file from job manager to local machine--------------------->")
            print(
                f"task_workflow_ids.csv File {remote_file_path} copied from {jobmanager_pod_name} to {local_task_workflow_ids_file} successfully.")

            # ........................... Start of c_ids creation for performance
            print("\nCreating a c_ids file that will be having the corelation ids, the file will be passed as argumemnt into performance testing\n")
            # Read the CSV file and extract corelationID values
            with open(local_task_workflow_ids_file, 'r', newline='') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    corelation_ids.append(row['corelationID'])
            # Write the corelationID values to the text file
            with open(c_ids_file, 'w') as txtfile:
                for corelation_id in corelation_ids:
                    txtfile.write(corelation_id + "\n")
            print(f'CorelationID values have been successfully written to {c_ids_file} for Performance testing.')
            # ...........................End of c_ids creation for performance

            return local_task_workflow_ids_file
        else:
            print(f"File {remote_file_path} did'nt get copy to local.")
    except subprocess.CalledProcessError as e:
        print(f"Error: File {remote_file_path} does not exist in {jobmanager_pod_name}. Copy operation aborted.")

def copy_email_logger_from_jobManager(remote_file_path, namespace, jobmanager_pod_name):
    # Construct the kubectl exec command to check if the file exists in the pod
    command_check_existence = f"kubectl exec -n {namespace} {jobmanager_pod_name} -- stat {remote_file_path}"
    # Execute the command to check if the file exists
    try:
        subprocess.run(command_check_existence, shell=True, check=True)
        print(f"File {remote_file_path} exists in {jobmanager_pod_name}. Proceeding with copying...")

        # Get the directory where the script is located
        script_directory = os.path.dirname(os.path.abspath(__file__))
        current_directory = script_directory

        # Create the logger directory if it doesn't exist
        logger_directory = os.path.join(current_directory, "logger")
        if not os.path.exists(logger_directory):
            os.makedirs(logger_directory)

        # Define the log file path
        local_email_log_file = os.path.join(logger_directory, "local_emailLogger.log")

        # local_email_log_file = current_directory + "/local_emailLogger.log"

        # Construct the kubectl cp command to copy the file from the pod
        command_copy_file = f"kubectl cp {namespace}/{jobmanager_pod_name}:{remote_file_path} {local_email_log_file}"
        # Execute the command to copy the file
        subprocess.run(command_copy_file, shell=True, check=True)
        if os.path.exists(local_email_log_file):
            print(
                "<-----------------Copying emailLogger.log file from job manager to local machine--------------------->")
            print(
                f"emailLogger.log File {remote_file_path} copied from {jobmanager_pod_name} to {local_email_log_file} successfully.")
            return local_email_log_file
        else:
            print(f"File {remote_file_path} did'nt get copy to local.")
    except subprocess.CalledProcessError as e:
        print(f"Error: File {remote_file_path} does not exist in {jobmanager_pod_name}. Copy operation aborted.")