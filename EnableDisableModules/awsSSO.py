import subprocess

def aws_sso_login():
    # Perform the AWS SSO login once at the start
    print("Please complete the AWS SSO login in your browser.")
    run_command("aws sso login --sso-session isv-sso", shell=True)
    print("AWS SSO login completed.")

def run_command(command, capture_output=False, shell=False):
    try:
        if capture_output:
            result = subprocess.run(command, shell=shell, capture_output=True, text=True, check=True)
            return result.stdout
        else:
            subprocess.run(command, shell=shell, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command '{e.cmd}' failed with return code {e.returncode}")
        print(f"Output: {e.output}")
        print(f"Error: {e.stderr}")
        raise

# aws_sso_login()