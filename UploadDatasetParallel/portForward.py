import os
import subprocess
import sys
import time
import re
import json
import signal
import requests

def pipeExtention_port_forward(kubeconfig_path, remote_port, NAMESPACE):
    print("<---------------Port Forward Pipe Extention port--------------->")
    # Set the KUBECONFIG environment variable
    # kubeconfig_path = kubeconfig_folder_path + kubeConfigFile
    os.environ["KUBECONFIG"] = kubeconfig_path
    # Get the name of the pipeExtention pod in the specified namespace
    result = subprocess.run(["kubectl", "get", "pods", "-n", NAMESPACE], capture_output=True, text=True, check=True)
    pipeExtention_pod = None
    for line in result.stdout.split('\n'):
        if "rapid-pipe" in line:
            print("rapid-pipe exists")
            pipeExtention_pod = line.split()[0]
            print(pipeExtention_pod)
            break

    # Check if a pipeExtention pod is found
    if not pipeExtention_pod:
        print(f"No Pipe Extention pod found in the {NAMESPACE} namespace.")
        sys.exit(1)

    # Perform port forwarding to a random local port
    process = subprocess.Popen(["kubectl", "port-forward", "-n", NAMESPACE, pipeExtention_pod, ":" + remote_port],
                               stdout=subprocess.PIPE)

    # Wait for a moment to ensure port forwarding is established
    time.sleep(1)

    # Check if the process started successfully and read its output
    if process.stdout:
        output = process.stdout.readline().decode().strip()
        print(output)

        # Use regex to extract the local port number
        match = re.search(r"Forwarding from \S+:(\d+)", output)
        if match:
            forwarded_port = match.group(1)
            # yielding the required forwarded_port. If we return it then the process will terminate. We want it to be in running state.
            yield forwarded_port
    else:
        print("Error: Unable to start port forwarding process")

    # Keep the script running
    while True:
        time.sleep(1)


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


def tomcatServer_port_forward(kubeconfig_path, local_port, remote_port, tomcatServer_username, tomcarServer_password, NAMESPACE):
    # Set the KUBECONFIG environment variable
    # kubeconfig_path = kubeconfig_folder_path + kubeConfigFile
    os.environ["KUBECONFIG"] = kubeconfig_path
    # Get the name of the tomcatServer pod in the specified namespace
    result = subprocess.run(["kubectl", "get", "pods", "-n", NAMESPACE], capture_output=True, text=True, check=True)
    tomcarServer_pod = None
    for line in result.stdout.split('\n'):
        if "rapid-tomcat" in line:
            tomcarServer_pod = line.split()[0]
            break

    # Check if a conductorUI pod is found
    if not tomcarServer_pod:
        print(f"No tomcarServer pod found in the {NAMESPACE} namespace.")
        sys.exit(1)

    # Perform port forwarding to a random local port
    process = subprocess.Popen(
        ["kubectl", "port-forward", tomcarServer_pod, "-n", NAMESPACE, local_port + ":" + remote_port],
        stdout=subprocess.PIPE)

    # Wait for a moment to ensure port forwarding is established
    time.sleep(1)

    # Check if the process started successfully and read its output
    if process.stdout:
        output = process.stdout.readline().decode().strip()
        print(output)

        # Use regex to extract the local port number
        match = re.search(r"Forwarding from \S+:(\d+)", output)
        if match:
            forwarded_port = match.group(1)
            yield forwarded_port
            # print(f"TomcatServer pod Port forwarded to: {forwarded_port}")
            #
            # # Fetch Authorization Token
            # url = f"https://localhost:{forwarded_port}/isvapi/service/v1/authenticate/loginx"
            # print(url)
            # body = {"password": tomcarServer_password, "username": tomcatServer_username}
            # payload = json.dumps(body)
            # headers = {'Content-Type': 'application/json'}
            # response = requests.post(url=url, headers=headers, data=payload)
            # print(response.headers)
            # print(type(response.headers))
            # return process

    else:
        print("Error: Unable to start port forwarding process")


    # Keep the script running
    # while True:
    #     time.sleep(1)


def getAuthToken(port, tomcatServer_password, tomcatServer_username):
    # Fetch Authorization Token
    print("\n")
    print("<---------------Fetching Authorization Token--------------->")
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
        return authorization_token