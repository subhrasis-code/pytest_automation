import csv
import os
import time
import json
import requests
import pandas as pd


def status(local_task_workflow_id_CSV_path, conductorUI_local_port):
    # Get the directory where the script is located
    script_directory = os.path.dirname(os.path.abspath(__file__))
    current_directory = script_directory
    results = {}

    # Create the logger directory if it doesn't exist
    logger_directory = os.path.join(current_directory, "logger")
    if not os.path.exists(logger_directory):
        os.makedirs(logger_directory)

    # Define the log file path
    log_file_path = os.path.join(logger_directory, "logger.json")
    with open(log_file_path, "w") as logFile:
        # Open the CSV file
        with open(local_task_workflow_id_CSV_path, newline='') as csvfile:
            # Create a CSV reader object
            reader = csv.reader(csvfile)
            # Skip the header row
            next(reader)

            # Iterate over each row in the CSV file
            for row in reader:
                correlation_id = row[2]
                search_workflows_url = f"http://localhost:{conductorUI_local_port}/api/workflow/search?start=0&size=5&sort=startTime%3ADESC&freeText={correlation_id}&query="

                try:
                    response = requests.get(url=search_workflows_url)
                    time.sleep(0.1)

                    if response.status_code == 200:
                        response_data = response.json()

                        if correlation_id not in results:
                            results[correlation_id] = {"workflows": []}

                        for item in response_data["results"]:
                            workflowId = item["workflowId"]
                            workflow_entry = {
                                "workflowType": item["workflowType"],
                                "workflowId": item["workflowId"],
                                "status": item["status"],
                                "tasks": []
                            }
                            results[correlation_id]["workflows"].append(workflow_entry)

                            subTasks_url = f"http://localhost:{conductorUI_local_port}/api/workflow/{workflowId}"
                            response_subtask = requests.get(url=subTasks_url)
                            time.sleep(0.1)

                            if response_subtask.status_code == 200:
                                response_subtask_data = response_subtask.json()
                                for element in response_subtask_data["tasks"]:
                                    taskType = element["taskType"]
                                    referenceTaskName = element["referenceTaskName"]
                                    taskId = element["taskId"]
                                    taskStatus = element["status"]
                                    workflow_entry["tasks"].append({
                                        "taskType": taskType,
                                        "referenceTaskName": referenceTaskName,
                                        "taskId": taskId,
                                        "taskStatus": taskStatus
                                    })
                except requests.exceptions.RequestException as e:
                    print(f"Error fetching data for {correlation_id}: {e}")

        # Write results to the log file
        logFile.write(json.dumps(results, indent=4))

    print(results)
    print(f"Result is ready in {current_directory}/logger.log.")


# status(
#     "/Users/subhrasis/Documents/Rapid_pythonScripts/Auto_modules_6_2/onPrem/fetchTaskIDWorkflowID/logger/local_task_workflow_ids.csv",
#     "5000")
