import requests
import urllib3
import time
from datetime import datetime

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def tomcatModuleStatusChecker(authorization_token, sitename, port, statusCheckInterval, max_retries=5):
    # Base URL
    url = f"https://localhost:{port}/isvapi/service/v1/patientmgmt/timeline?filter=today&sitename={sitename}"

    # Define request headers
    headers = {
        'Authorization': str(authorization_token)
    }

    retry_count = 0

    while True:
        try:
            # Send GET request to the API
            response = requests.get(url, headers=headers, verify=False)  # verify=False if using self-signed SSL certificate

            # Check and process the response
            if response.status_code == 200:
                response_data = response.json()
                patientlist = response_data.get("patientlist", [])
                running_task_found = False

                if len(patientlist) > 0:
                    for patient in patientlist:
                        if "patienttasklist" in patient:
                            patienttasklist = patient["patienttasklist"]
                            for patienttask in patienttasklist:
                                if patienttask['taskstatus'] == "RUNNING":
                                    print(
                                        f"taskstatus: {patienttask['taskstatus']}, patientId: {patient['patient']['patientId']}, patientName: {patient['patient']['patientName']}, modulename: {patienttask['modulename']}, taskid: {patienttask['taskid']}, scheduleddatetime: {patienttask['scheduleddatetime']}, startdatetime: {patienttask['startdatetime']}")
                                elif patienttask['taskstatus'] == "SCHEDULED":
                                    print(
                                        f"taskstatus: {patienttask['taskstatus']}, patientId: {patient['patient']['patientId']}, patientName: {patient['patient']['patientName']}, modulename: {patienttask['modulename']}, taskid: {patienttask['taskid']}, scheduleddatetime: {patienttask['scheduleddatetime']}")
                                else:
                                    startdatetime = patienttask['startdatetime']
                                    enddatetime = patienttask['enddatetime']

                                    # Convert strings to datetime objects
                                    start_dt = datetime.strptime(startdatetime, "%Y-%m-%d %H:%M:%S.%f")
                                    end_dt = datetime.strptime(enddatetime, "%Y-%m-%d %H:%M:%S.%f")

                                    # Calculate the difference
                                    time_difference = str(end_dt - start_dt)

                                    print(
                                        f"taskstatus: {patienttask['taskstatus']}, patientId: {patient['patient']['patientId']}, patientName: {patient['patient']['patientName']}, modulename: {patienttask['modulename']}, taskid: {patienttask['taskid']}, scheduleddatetime: {patienttask['scheduleddatetime']}, startdatetime: {patienttask['startdatetime']}, enddatetime: {patienttask['enddatetime']}, time_difference: {time_difference}")
                        print("\n")

                    for patient in patientlist:
                        if "patienttasklist" in patient:
                            patienttasklist = patient["patienttasklist"]
                            for patienttask in patienttasklist:
                                if patienttask.get("taskstatus", "").upper() in ["RUNNING", "SCHEDULED"]:
                                    print("Image Processing is still going On")
                                    running_task_found = True
                                    break  # Exits the innermost for loop
                        if running_task_found:
                            break  # as running_task_found = True no need to check other patients

                if not running_task_found:
                    print("Every module's Image Processing completed")
                    break  # Exits the while loop

            else:
                print(f"Error: {response.status_code}, {response.text}")
                break  # Exits the while loop if there's an error

            # Reset retry count after a successful request
            retry_count = 0

        except requests.exceptions.RequestException as e:
            retry_count += 1
            print(f"Connection error: {e}")
            if retry_count > max_retries:
                print("Max retries exceeded. Exiting...")
                break  # Exits the while loop after max retries

        # Wait before checking again
        print(f"Waiting for {statusCheckInterval} seconds to re-check the status...")
        time.sleep(statusCheckInterval)
        print("\n")

# authorization_token = "Token OTc0N2Y5YWMtMzM3OC00MmRjLWFkNDEtY2JiOGJkMDYwOTc5fGlzdmFkbWlufDIwMjQvMDYvMTIgMTA6NTY6NDA="
# sitename = "parakeet_demo"
# port = 8443
#
# # Call the function
# tomcatModuleStatusChecker(authorization_token, sitename, port)
