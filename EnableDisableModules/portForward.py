import os
import subprocess
import sys
import time
import re
import requests
import json

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