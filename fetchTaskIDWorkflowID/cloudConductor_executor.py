from cloudConductor_functions import get_cloud_workflowID, get_logs
import os
import csv


def runner(conductor_pod_name, remote_port, local_port, check_corelationIds, region, profile, cluster_name, alias, namespace):
    # Get the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = script_directory
    # print(current_directory)

    # Create the logger directory if it doesn't exist
    logger_directory = os.path.join(current_directory, "logger")
    if not os.path.exists(logger_directory):
        os.makedirs(logger_directory)

    # Define the log file path
    log_file_path = os.path.join(logger_directory, "failureCloud.log")

    # with open(current_directory + "/failureCloud.log", "w") as logFile:
    with open(log_file_path, "w") as logFile:
        logs = ""
        # check_corelationIds = [{'7c7d3a07-afc0-43a7-9525-a6e049ff099a': '/rapid_data/task_data/site1/ANRTN/2606_8018'},
        #                        {'be5d93d2-c93b-421e-80de-a06d0087d343': '/rapid_data/task_data/site1/neuro3d/2553_7963'}]
        print("Inside cloud_executor runner function.")
        for item in check_corelationIds:
            for corelationId in item.keys():
                OnPremResultsDir = item[corelationId]
                failed_initCloud_workflowIds, passed_initCloud_workflowIds = get_cloud_workflowID(corelationId, local_port)

                print(f"corelationID : {corelationId}")
                print(f"List of Failed initCloud workflowIds : {failed_initCloud_workflowIds}")
                print(f"List of Passed initCloud workflowIds : {passed_initCloud_workflowIds}")
                print("\n")

                if failed_initCloud_workflowIds:
                    failed_log_detail = get_logs(failed_initCloud_workflowIds, local_port, corelationId, OnPremResultsDir)
                    print(failed_log_detail)
                    logs += failed_log_detail
                    logs += "\n\n"
        return logs

def module_checker(local_task_workflow_ids_file, cloud_processing_flag):
    list_corelationIds = []
    with open(local_task_workflow_ids_file, newline='') as csvfile:
        # Create a CSV reader object
        reader = csv.reader(csvfile)
        # Skip the header row
        next(reader)
        if cloud_processing_flag == "False":
            # Iterate over each row in the CSV file
            for row in reader:
                # Extract CorelationId (assuming it's in the second column)
                OnPremResultsDir = row[0]
                corelationID = row[2]
                PatientID = row[4]

                if "ANRTN" in OnPremResultsDir or "neuro3d" in OnPremResultsDir:
                    corelation_dict = {}
                    corelation_dict[corelationID] = OnPremResultsDir
                    list_corelationIds.append(corelation_dict)
        else:
            # Iterate over each row in the CSV file
            for row in reader:
                corelation_dict = {}
                # Extract CorelationId (assuming it's in the second column)
                OnPremResultsDir = row[0]
                corelationID = row[2]
                PatientID = row[4]
                corelation_dict[corelationID] = OnPremResultsDir
                list_corelationIds.append(corelation_dict)

    return list_corelationIds if list_corelationIds else None

