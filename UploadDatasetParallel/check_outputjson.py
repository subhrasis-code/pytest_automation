import subprocess
import json
import os

# Keys you want to extract
keys_to_extract = ["ReturnCodeDescription", "ReturnCode", "ProcessingTimeInSeconds", "ProcessingTimeSeconds", "processingTimeInSeconds",
                   "NumberOfSlices", "NumberOfSlicesAffected", "RVLVRatio", "ich_version", "HemorrhageDetected", "scoreLeftHemisphere",
                   "scoreRightHemisphere", "aspects_version", "Region", "LVOOnNCCTSuspected", "AneurysmSuspected", "valueString",
                   "scanCaution", "scanRejected", "LVODetectionEnabled", "LVODetected", "USAVersionLimitation", "VesselDensityRatio",
                   "Description", "ModuleName", "moduleName", "ArtifactsDetected"]

diagnosis_modules = {
                "Rapid PE" : "Description",
                "ICH": "HemorrhageDetected",
                "SDH" : "SDHSuspected",
                "NCCT Stroke" : "LVOOnNCCTSuspected",
                "CINA_IPE" : "valueString",
                "ANRTN" : "AneurysmSuspected",
                "CTA" : "LVODetected",
                "LVO" : "LVODetected",
                "CTA/LVO" : "LVODetected"
                }

anatomy_modules = {}

# Read a specific output.json file from the pod
def read_json_from_pod(json_path, kubeconfig_path, pod_name, namespace):
    cmd = [
        "kubectl", "--kubeconfig", kubeconfig_path, "-n", namespace,
        "exec", pod_name, "--", "cat", json_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"Error reading {json_path}: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in {json_path}: {e}")
        return None

def find_key_recursive(json_data, target_key):
    """
    Recursively search for a key in a nested dictionary/list.
    Returns the first value found for the key.
    """
    if isinstance(json_data, dict):
        for key, value in json_data.items():
            if key == target_key:
                return value
            result = find_key_recursive(value, target_key)
            if result is not None:
                return result
    elif isinstance(json_data, list):
        for item in json_data:
            result = find_key_recursive(item, target_key)
            if result is not None:
                return result
    return None

def check_outputjson_main(json_path, kubeconfig_path, pod_name, namespace):
    print(f"Starting to check keys in Output Json file for : {json_path}")
    json_data = read_json_from_pod(json_path, kubeconfig_path, pod_name, namespace)

    values = []
    for key in keys_to_extract:
        value = find_key_recursive(json_data, key)
        # print(value)
        if value is None:
            continue  # Skip if value is None
        if isinstance(value, dict):
            values.append(f"{key}: {value}")
        else:
            values.append(f"{key}: {value}")

    print(" | ".join(values) + f" | {json_path}")

    # Convert list of "Key: Value" strings to a dictionary
    info_dict = dict(item.split(': ') for item in values)

    moduleName = info_dict.get("ModuleName")
    if moduleName in diagnosis_modules:
        diagnos_param_key = diagnosis_modules.get(moduleName)
        diagnos_param_value = info_dict.get(diagnos_param_key)
        print(f"{moduleName} is processed successfully and {diagnos_param_key} is {diagnos_param_value}")
    else:
        returncode = info_dict.get("ReturnCode:")
        print(f"{moduleName} is processed successfully and ReturnCode is {returncode} ")

    # Now locate and read workflow_input.json
    # base_dir = os.path.dirname(json_path)
    # workflow_input_path = os.path.join(base_dir, "workflow_input.json")
    # workflow_data = read_json_from_pod(workflow_input_path, kubeconfig_path, pod_name, namespace)
    #
    # if workflow_data:
    #     workflow_id = find_key_recursive(workflow_data, "workflowID")
    #     corelation_id = find_key_recursive(workflow_data, "corelationID")
    #     print(f"workflowID: {workflow_id} | corelationID: {corelation_id} | {workflow_input_path} \n")
    # else:
    #     print(f"Could not read or parse workflow_input.json at {workflow_input_path}")

# json_path = "/rapid_data/task_data/site2/Hyperdensity/110_383/output.json"
# # Configuration
# kubeconfig_path = "/Users/zinnov/Documents/Rapid/Performance/kubeConfigFiles/admin.ipe-op.kubeconfig"  # Update path
# pod_name = "rapid-jobmanager-894dd6b67-9dcs2"  # Update pod name
# namespace = "rapid-apps"

# check_outputjson_main(json_path, kubeconfig_path, pod_name, namespace)