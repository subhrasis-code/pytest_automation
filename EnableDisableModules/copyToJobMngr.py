import subprocess

def copy_file_to_jobManager(local_file_path, remote_file_path, namespace, jobmanager_pod_name):
    # Construct the kubectl cp command to copy the file to the pod
    command = f"kubectl cp {local_file_path} {namespace}/{jobmanager_pod_name}:{remote_file_path}"

    # Execute the command
    subprocess.run(command, shell=True, check=True)
    print(f"File {local_file_path} copied to {remote_file_path} successfully.")