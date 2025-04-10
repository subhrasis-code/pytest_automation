import requests
import json
import time
import psutil
import warnings
import subprocess
import signal
import os
from urllib3.exceptions import InsecureRequestWarning

# Filter out the InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

def getAuthToken(port, tomcatServer_password, tomcatServer_username, moduleToEnable, siteName, userEmailList):
    # Fetch Authorization Token
    print("\n")
    print("Step 7 <---------------Fetching Authorization Token--------------->")
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
        executor(moduleToEnable, authorization_token, siteName, port, userEmailList)
        time.sleep(10)
        logout_user(port, authorization_token)

# def terminate_port_forward():
#     for process in psutil.process_iter():
#         try:
#             # Check if the process name matches kubectl
#             if process.name() == "kubectl":
#                 # Terminate the process
#                 process.terminate()
#                 print("Tomcat Port forwarding process terminated Successfully.")
#                 print("\n")
#         except psutil.NoSuchProcess:
#             pass

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

def enableDicomAPI(moduleName_in_payload, siteName, authorization_token, port):
    # Define endpoint URL
    url = f"https://localhost:{port}/isvapi/service/v1/configmgmt/dicomsettings"
    # Define payload data
    payload = {
        "sitename": str(siteName),
        "module": str(moduleName_in_payload),
        "aetindex": 15,
        "groupid": -1
    }

    # Define request headers
    headers = {
        'Authorization': str(authorization_token),
        'Content-Type': 'application/json'
    }

    try:
        # Send PUT request with payload as JSON string
        response = requests.put(url=url, headers=headers, json=payload, verify=False)
        # Check response status code
        if response.status_code == 200:
            print(f"Activated Dicom Send for {moduleName_in_payload} successfully.")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)  # Print response body for further debugging if needed
    except requests.exceptions.RequestException as e:
        print("Error:", e)

def enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList, userEmailgroupId):
    # Define endpoint URL
    url = f"https://localhost:{port}/isvapi/service/v1/configmgmt/emailsettings"
    # Define payload data
    payload = {
        "module": str(moduleName_in_payload),
        "sitename": str(siteName),
        "emaillist": userEmailList,
        "groupid": userEmailgroupId
    }

    # Define request headers
    headers = {
        'Authorization': str(authorization_token),
        'Content-Type': 'application/json'
    }

    try:
        # Send PUT request with payload as JSON string
        response = requests.put(url=url, headers=headers, json=payload, verify=False)
        # Check response status code
        if response.status_code == 200:
            print(f"Activated User Email for {moduleName_in_payload} successfully.")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)  # Print response body for further debugging if needed
    except requests.exceptions.RequestException as e:
        print("Error:", e)

def executor(moduleToEnable, authorization_token, siteName, port, userEmailList):
    print("\n")
    print("Step 8 <---------------Enabling Dicom Send and User Email for the given modules--------------->")
    # print(moduleToEnable)
    for module in moduleToEnable:
        if module == "<hypodensitystandalone>":
            moduleName_in_payload = "hypodensity"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=0)
        elif module == "<enablehyperdensity>":
            moduleName_in_payload = "hyperdensity"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=0)
        elif module == "<enableaspects>":
            moduleName_in_payload = "octopus"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=4)
        elif module == "<enableanrtn>":
            moduleName_in_payload = "anrtn"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=0)
        elif module == "<enableneuro3d>":
            moduleName_in_payload = "neuro3d"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=0)
        elif module == "<enablencctstroke>":
            moduleName_in_payload = "ncctstroke"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=0)
        elif module == "<enablervlv>":
            moduleName_in_payload = "rvlv"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=0)
        elif module == "<enablepetn>":
            moduleName_in_payload = "petn"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=0)
        elif module == "<enablemismatch>":
            moduleName_in_payload = "Mismatch"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=2)
        elif module == "<enablecta>":
            moduleName_in_payload = "angio"
            enableDicomAPI( moduleName_in_payload, siteName, authorization_token, port)
            enableUserEmailAPI(moduleName_in_payload, siteName, authorization_token, port, userEmailList,
                               userEmailgroupId=5)


