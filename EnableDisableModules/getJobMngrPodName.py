import subprocess

def get_jobmanager_postgres_pod(namespace):
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
            # print(elements)
            # Check if the line contains "rapid-jobmanager" and the pod is in running state
            if "rapid-jobmanager" in elements[0] and elements[2] == "Running":
            # if "rapid-pipe" in elements[0] and elements[2] == "Running":
                # Print the pod name
                jobmanager_pod_name = elements[0]

            if "postgres" in elements[0] and elements[2] == "Running":
                # Print the pod name
                postgres_pod_name = elements[0]

            if "rapid-pipe" in elements[0] and elements[2] == "Running":
            # if "rapid-pipe" in elements[0] and elements[2] == "Running":
                # Print the pod name
                pipeExtention_pod_name = elements[0]
        # Return the output of the command
        return jobmanager_pod_name, postgres_pod_name, pipeExtention_pod_name
    else:
        # Return the error message if the command failed
        return result.stderr.strip()