import subprocess

def get_jobmanager_conductorUI_pod(namespace):
    # Construct the kubectl command to get pods in the specified namespace
    command = f"kubectl get pods -n {namespace}"
    # Execute the kubectl command
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    # Check if the command executed successfully
    if result.returncode == 0:
        output = result.stdout.strip()
        # Split the output into lines
        lines = output.strip().split('\n')
        # Iterate through each line
        for line in lines:
            # Split the line by whitespace
            elements = line.split()
            print(elements)
            # Check if the line contains "rapid-jobmanager" and the pod is in running state
            if "rapid-jobmanager" in elements[0] and elements[2] == "Running":
            # if "rapid-pipe" in elements[0] and elements[2] == "Running":
                # Print the pod name
                jobmanager_pod_name = elements[0]

            if "conductor-ui" in elements[0] and elements[2] == "Running":
                # Print the pod name
                conductorUI_pod_name = elements[0]

            if "conductor-server" in elements[0] and elements[2] == "Running":
                # Print the pod name
                onPrem_conductorServer_pod_name = elements[0]
        # Return the output of the command
        return jobmanager_pod_name, conductorUI_pod_name, onPrem_conductorServer_pod_name
    else:
        # Return the error message if the command failed
        return result.stderr.strip()