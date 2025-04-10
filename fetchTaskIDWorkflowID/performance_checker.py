import os
import subprocess
from cloudConductor_functions import terminate_port_forward, aws_sso_login, get_k8s_pods

# Define variables for on-prem and cloud configurations
# onPrem_kubeconfig = "/Users/subhrasis/Documents/Rapid_pythonScripts/Performance/kubeConfigFiles/admin.testsinglenode.kubeconfig"
# # onPrem_conductor_server = "conductor-server-655b598c7-xr59fqdhjbwehj"
# onPrem_local_port = "8080"
# onPrem_remote_port = "8080"
# #
# onCloud_kubeconfig = "/Users/subhrasis/Documents/Rapid_pythonScripts/Performance/kubeConfigFiles/admin.alpha-sandpit67f333.kubeconfig"
# # onCloud_conductor_server = "conductor-server-fd8c47d8c-29kt6jhbsdfjhcb"
# onCloud_local_port = "8081"
# onCloud_remote_port = "8080"
# #
# # # Get the directory where the script is located
# # # script_directory = os.path.dirname(os.path.abspath(__file__))
# # # current_directory = script_directory
# # #
# duration = "24h"
# # # wftrackerpy_file_path = os.path.join(current_directory,"wftracker.py")
# # # performance_report_path = os.path.join(current_directory,"logger")
# # # c_ids_file_path = os.path.join(current_directory,"logger", "c_ids")
# #
# # # wftrackerpy_file_path = "/Users/subhrasis/Documents/Rapid_pythonScripts/Automation/fetchTaskIDWorkflowID/wftracker.py"
# # # c_ids_file_path = "/Users/subhrasis/Documents/Rapid_pythonScripts/Automation/fetchTaskIDWorkflowID/logger/c_ids"
# # # performance_report_path = "/Users/subhrasis/Documents/Rapid_pythonScripts/Automation/fetchTaskIDWorkflowID/logger/"
# #
# namespace = "rapid-apps"

def performance_executor(onPrem_kubeconfig, onPrem_local_port, onPrem_remote_port,
                         onCloud_kubeconfig, onCloud_local_port, onCloud_remote_port, duration, namespace):
    try:
        print("Inside performance_executor")

        # Perform AWS SSO login if necessary (uncomment if required)
        # aws_sso_login()

        # Get the directory where the script is located
        script_directory = os.path.dirname(os.path.abspath(__file__))
        current_directory = script_directory

        wftrackerpy_file_path = os.path.join(current_directory, "wftracker.py")
        wf_runner_file_path = os.path.join(current_directory, "wf_runner.sh")
        os.chmod(wf_runner_file_path, 0o755)
        performance_report_path = os.path.join(current_directory, "logger")
        c_ids_file_path = os.path.join(current_directory, "logger", "c_ids")

        print(current_directory)
        print(wftrackerpy_file_path)
        print(wf_runner_file_path)
        print(performance_report_path)
        print(c_ids_file_path)


        # # Terminate any existing port forwarding
        # terminate_port_forward()
        #
        pod_type = "conductor-server"
        #
        try:
            onPrem_conductor_server = str(get_k8s_pods(namespace, onPrem_kubeconfig, pod_type))
            print(f"\nonPrem_conductor_server: {onPrem_conductor_server}")
            onCloud_conductor_server = str(get_k8s_pods(namespace, onCloud_kubeconfig, pod_type))
            print(f"onCloud_conductor_server: {onCloud_conductor_server}\n")
            # onCloud_conductor_server = "conductor-server-ccbc7c6b9-n6vv4"
        except Exception as e:
            print(f"Error getting k8s pods: {e}")
            return

        # print(f"\nonPrem_conductor_server: {onPrem_conductor_server}")
        # print(f"onCloud_conductor_server: {onCloud_conductor_server}\n")

        # Command to execute the shell script with parameters
        command = [
            wf_runner_file_path,
            onPrem_kubeconfig, onPrem_conductor_server, onPrem_local_port, onPrem_remote_port,
            onCloud_kubeconfig, onCloud_conductor_server, onCloud_local_port, onCloud_remote_port,
            wftrackerpy_file_path, duration, c_ids_file_path, performance_report_path, namespace
        ]

        print(command)

        try:
            # Run the shell script with the provided arguments
            result = subprocess.run(command, text=True, check=True)
            print("Performance Command executed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Performance Command execution failed: {e}")
            print(f"Performance Command output: {e.output}")
        except Exception as e:
            print(f"Unexpected error during Performance command execution: {e}")

    except Exception as e:
        print(f"Unexpected error in performance_executor: {e}")

    # Terminate any existing port forwarding
    # terminate_port_forward()

# performance_executor(onPrem_kubeconfig, onPrem_local_port, onPrem_remote_port, onCloud_kubeconfig,
#                      onCloud_local_port, onCloud_remote_port, duration, namespace)
