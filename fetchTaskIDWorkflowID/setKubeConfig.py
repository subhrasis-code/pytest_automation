import os

def set_kubeconfig(kubeconfig_path):
    # Set the KUBECONFIG environment variable
    os.environ['KUBECONFIG'] = kubeconfig_path
    print(f"\nKUBECONFIG set to ----> {kubeconfig_path} \n")