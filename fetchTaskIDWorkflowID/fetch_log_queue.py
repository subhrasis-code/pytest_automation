import requests
import os
import json
import time
import psutil
import warnings
import subprocess
import signal
from urllib3.exceptions import InsecureRequestWarning

# Filter out the InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# def terminate_port_forward():
#     for process in psutil.process_iter():
#         try:
#             # Check if the process name matches kubectl
#             if process.name() == "kubectl":
#                 # Terminate the process
#                 process.terminate()
#                 print("kubectl process terminated Successfully.")
#                 print("\n")
#         except psutil.NoSuchProcess:
#             pass

def terminate_port_forward():
    try:
        # List all processes and filter by name 'kubectl'
        result = subprocess.run(["pgrep", "-f", "kubectl"], capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                    print(f"Terminated kubectl process with PID {pid}")
                except PermissionError as e:
                    print(f"Permission denied when trying to terminate process with PID {pid}: {e}")
                except Exception as e:
                    print(f"Error when trying to terminate process with PID {pid}: {e}")
        else:
            print("No kubectl processes found.")
    except Exception as e:
        print(f"Failed to list or terminate kubectl processes: {e}")

def logout_user(port, authorization_token):
    url = f"https://localhost:{port}/isvapi/service/v1/authenticate/logoutx"

    # Define request headers
    headers = {
        'Authorization': str(authorization_token)
    }

    try:
        # Send DELETE request with payload as JSON string
        response = requests.delete(url=url, headers=headers, verify=False)
        # Check response status code
        if response.status_code == 200:
            print(f"Logged out tomcat user successfully.")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)  # Print response body for further debugging if needed
    except requests.exceptions.RequestException as e:
        print("Error:", e)

def getAuthToken(port, tomcatServer_password, tomcatServer_username, site_name, log_filename=None):
    # Fetch Authorization Token
    print("\n")
    print("Step [7] <---------------Fetching Authorization Token--------------->")
    # print(moduleToEnable)
    url = f"https://localhost:{port}/isvapi/service/v1/authenticate/loginx"
    body = {"password": tomcatServer_password, "username": tomcatServer_username}
    payload = json.dumps(body)
    headers = {'Content-Type': 'application/json'}
    time.sleep(1)

    # as tomcat port forward status use to fluctuate, so to get proper 200ok we segregated auth token api to a nested method.
    # Added retry logic if we dont get 200 ok at 1st attempt
    def call_auth_token_api(url, headers, payload, max_retries=15):
        for attempt in range(1, max_retries + 1):
            # Disable Certificate Verification by doing verify=False
            response = requests.post(url=url, headers=headers, data=payload, verify=False)
            if response.status_code == 200:
                # Check if the 'Authorization' header is present in the response
                if 'Authorization' in response.headers:
                    # Print the value of the 'Authorization' header
                    authorization_token = response.headers['Authorization']
                    print('Authorization Token:', authorization_token)
                    return authorization_token
                else:
                    print('Authorization header not found in response')
            else:
                print(
                    f"Fetch Authorization Token Request was not successful. Status code: {str(response.status_code)}. Retrying...")
                time.sleep(1.5)
        # if after all retries we dont get 200 OK, then NONE will be returned
        return None
    #
    authorization_token = call_auth_token_api(url, headers, payload)
    if authorization_token == None:
        print("Auth token API call failed after maximum retries.")
    # it will come inside else when we get the auth token from call_auth_token_api() method
    else:
        dicom_url = f"https://localhost:{port}/isvapi/service/v1/patientmgmt/dicomqueue?sitename={site_name}"
        email_url = f"https://localhost:{port}/isvapi/service/v1/patientmgmt/emailqueue?sitename={site_name}"

        # Fetch Dicom Log Queue
        fetch_and_log_queue(dicom_url, authorization_token, "dicom_queue.log")
        # Fetch Email Log Queue
        fetch_and_log_queue(email_url, authorization_token, "email_queue.log")

        fetch_and_log_queue(url, authorization_token, log_filename)

        time.sleep(10)
        logout_user(port, authorization_token)


def fetch_and_log_queue(url, authorization_token, log_filename):
    headers = {
        'Authorization': str(authorization_token),
        'Content-Type': 'application/json'
    }
    response = requests.get(url=url, headers=headers, verify=False)
    if response.status_code == 200:
        # response.content is in bytes format
        bytes_data = response.content
        # Decode bytes to string
        string_data = bytes_data.decode('utf-8')
        # Parse string to dictionary
        dictionary_data = json.loads(string_data)

        # Specify the log file path
        # Get the directory where the script is located
        script_directory = os.path.dirname(os.path.abspath(__file__))
        current_directory = script_directory

        # Create the logger directory if it doesn't exist
        logger_directory = os.path.join(current_directory, "logger")
        if not os.path.exists(logger_directory):
            os.makedirs(logger_directory)

        log_file_path = os.path.join(logger_directory, log_filename)

        # Write the dictionary to the log file in beautified format
        with open(log_file_path, 'w') as log_file:
            json.dump(dictionary_data, log_file, indent=4)
        print("\n")
        print(f"{log_filename.capitalize()} logs have been written to the log file:", log_file_path)
        print("\n")
    else:
        print(f"Failed to fetch {log_filename} queue data. Status code: {response.status_code}")