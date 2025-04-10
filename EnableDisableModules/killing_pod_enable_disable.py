import subprocess
import time


def pod_kill(pod_prefix, namespace):

    try:
        # List all pods in the namespace
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "jsonpath={.items[*].metadata.name}"],
            check=True,
            capture_output=True,
            text=True
        )

        pod_names = result.stdout.split()
        for pod_name in pod_names:
            if pod_name.startswith(pod_prefix):
                print(f"Deleting pod: {pod_name}")
                subprocess.run(
                    ["kubectl", "delete", "pod", pod_name, "-n", namespace],
                    check=True
                )

        # Wait for 30 seconds
        print(f"Waiting for 20 seconds to restart {pod_prefix} pod......")
        time.sleep(20)
        print("Done waiting.")

    except subprocess.CalledProcessError as e:
        print(f"An error occurred: {e}")
