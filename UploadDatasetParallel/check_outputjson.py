import subprocess
import json
import os
import time
from datetime import datetime


# Keys to look for
keys_to_extract = ["ReturnCodeDescription", "returnCodeDescription", "ReturnCode", "ProcessingTimeInSeconds", "ProcessingTimeSeconds", "processingTimeInSeconds",
                   "NumberOfSlices", "NumberOfSlicesAffected", "RVLVRatio", "ich_version", "HemorrhageDetected", "scoreLeftHemisphere",
                   "scoreRightHemisphere", "aspects_version", "Region", "NCCTStrokeLVOSuspected", "AneurysmSuspected", "valueString",
                   "scanCaution", "scanRejected", "LVODetectionEnabled", "LVODetected", "USAVersionLimitation", "VesselDensityRatio",
                   "Description", "ModuleName", "moduleName", "ArtifactsDetected", "NCCTArtifactsJSONFilename", "SDHSuspected"]


diagnosis_modules = {
    "Rapid PE": {
        "positive": {"Description": "Suspected PE"},
        "negative": {"Description": "CTPA processed.\nPlease review source images."}
    },
    "ICH": {
        "positive": {"HemorrhageDetected": "True"},
        "negative": {"HemorrhageDetected": "False"},
    },
    "SDH": {
        "positive": {"SDHSuspected": "True"},
        "negative": {"SDHSuspected": "False"}
    },
    "NCCT Stroke": {
        "positive": {"NCCTStrokeLVOSuspected": "True"},
        "negative": {"NCCTStrokeLVOSuspected": "False"}
    },
    "CINA_IPE": {
        "positive": {"valueString": "SUSPECTED"},
        "negative": {"valueString": "PROCESSED"},
        "error": {"returnCodeDescription": "Input DICOM data invalid"}
    },
    "ANRTN": {
        "positive": {"AneurysmSuspected": "True"},
        "negative": {"AneurysmSuspected": "False"}
    },
    "CTA": {
        "positive": {"LVODetected": "True"},
        "negative": {"LVODetected": "False"}
    },
    "LVO": {
        "positive": {"LVODetected": "True"},
        "negative": {"LVODetected": "False"}
    },
    "CTA/LVO": {
        "positive": {"LVODetected": "True"},
        "negative": {"LVODetected": "False"}
    }
}

anatomy_modules = {
    "Rapid RV/LV": {"ReturnCode": 0},
    "Rapid Hyperdensity": {"ReturnCode": 0},
    "Hypodensity": {"ReturnCode": 0},
    "RAPIDNEURO3D": {"ReturnCode": 0},
    "ASPECTS1": {"ReturnCode": 0},
    "ASPECTS3": {"ReturnCode": 0},
    "Mismatch": {"ReturnCode": 0}
    }


# Global trackers
_pending_tests = []
_printed_paths = set()
_start_time = time.time()
_log_file_path = "check_outputjson_results.log"

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

def check_outputjson_executor(json_path, kubeconfig_path, pod_name, namespace, module_name):
    if json_path not in _printed_paths:
        print(f"📄 output.json created: {json_path}")
        _printed_paths.add(json_path)
        case_name = os.path.basename(os.path.dirname(json_path))
        _pending_tests.append((module_name, case_name, json_path, kubeconfig_path, pod_name, namespace))
        print("Going out of check_outputjson_executor method")

def execute_all_tests():
    total = len(_pending_tests)
    print("\n============================= test session starts =============================")
    print(f"collected {total} items")

    results = []

    for idx, (module_name, case_name, json_path, kubeconfig_path, pod_name, namespace) in enumerate(_pending_tests, 1):
        progress = int((idx / total) * 100)
        print(f"\nValidation for output.json::[{module_name}_{case_name}] PASSED [{progress}%]")

        json_data = read_json_from_pod(json_path, kubeconfig_path, pod_name, namespace)
        if not json_data:
            results.append((module_name, json_path, False, "Failed to read or parse JSON"))
            continue

        extracted_values = []
        for key in keys_to_extract:
            value = find_key_recursive(json_data, key)
            if value is None:
                continue  # Skip if value is None
            if isinstance(value, dict):
                extracted_values.append(f"{key}: {value}")
            else:
                extracted_values.append(f"{key}: {value}")

        # Convert list of "Key: Value" strings to a dictionary
        info_dict = {}
        for item in extracted_values:
            if ": " in item:
                key, value = item.split(": ", 1)
                info_dict[key] = value

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"\n[{timestamp}] " + " | ".join(extracted_values) + f" | {json_path}"
        try:
            with open(_log_file_path, "a") as log_file:
                log_file.write(log_entry + "\n")
        except Exception as e:
            print("⚠️ Failed to write log:", e)

        status = True
        fail_reason = ""
        dataset_type = None
        expected_key = None
        actual_value = None
        possible_module_name_keys = ["ModuleName", "moduleName", "modulename"]
        moduleName = next((info_dict.get(key) for key in possible_module_name_keys if info_dict.get(key)), "UnknownModule")

        if moduleName in diagnosis_modules:
            overall_map = diagnosis_modules[moduleName]
            matched_dataset = False

            def validate_dataset_type(moduleName, json_path, info_dict, dataset_types, overall_map):
                for dataset_type in dataset_types:
                    dataset_detail = overall_map.get(dataset_type)
                    if not dataset_detail:
                        continue
                    # Check one key-value pair to determine if this is the right dataset type
                    expected_key, expected_value = list(dataset_detail.items())[0]
                    actual_value = info_dict.get(expected_key)

                    if actual_value == expected_value:
                        # print(f"[{moduleName}] {json_path}: 🔍 Detected as [{dataset_type}] dataset")
                        for expected_key, expected_value in dataset_detail.items():
                            # now validate all keys under it
                            # Re-fetch for each key
                            actual_value = info_dict.get(expected_key)
                            # print(f"[{moduleName}] {json_path}: 🧪 Validating [{dataset_type}] {expected_key}...")
                            try:
                                # print(
                                #     f"[{moduleName}] {json_path}: ✅ PASSED - [{dataset_type}] {expected_key} = {actual_value}")
                                assert actual_value == expected_value, (
                                    f"[{moduleName}] {json_path}: ❌ FAILED - [{dataset_type}] Expected {expected_key}={expected_value}, | Actual {expected_key}={actual_value}"
                                )
                            except AssertionError as e:
                                nonlocal status, fail_reason # <-- this line lets us modify outer variables
                                status = False
                                fail_reason = str(e)
                                print(fail_reason)
                        return True  # ✅ Matching dataset found
                return False  # ❌ No match

            if moduleName != "CINA_IPE":
                matched_dataset = validate_dataset_type(moduleName, json_path, info_dict, ["positive", "negative"], overall_map)
                if not matched_dataset:
                    status = False
                    positive_map = overall_map["positive"]
                    negative_map = overall_map["negative"]
                    positive_key, positive_value = list(positive_map.items())[0]
                    negative_key, negative_value = list(negative_map.items())[0]
                    actual_value = info_dict.get(positive_key)
                    fail_reason = (
                        f"[{module_name}] {json_path}: ❌ FAILED - '{positive_key} : {actual_value}' does not match either:\n"
                        f"🔸 Positive: {positive_key} = {positive_value}\n"
                        f"🔹 Negative: {negative_key} = {negative_value}"
                    )
                    print(fail_reason)

            # elif moduleName == "ICH":
                # matched_dataset = validate_dataset_type(moduleName, json_path, info_dict, ["positive", "negative", "ncctArtifactDetection_positive", "ncctArtifactDetection_negative"], overall_map)

            else:  # For CINA_IPE
                matched_dataset = validate_dataset_type(moduleName, json_path, info_dict, ["positive", "negative", "error"], overall_map)
                if not matched_dataset:
                    status = False
                    positive_map = overall_map["positive"]
                    negative_map = overall_map["negative"]
                    error_map = overall_map["error"]
                    positive_key, positive_value = list(positive_map.items())[0]
                    negative_key, negative_value = list(negative_map.items())[0]
                    error_key, error_value = list(error_map.items())[0]
                    actual_value = info_dict.get(positive_key)
                    fail_reason = (
                        f"[{module_name}] {json_path}: ❌ FAILED - '{positive_key} : {actual_value}' does not match either:\n"
                        f"🔸 Positive: {positive_key} = {positive_value}\n"
                        f"🔹 Negative: {negative_key} = {negative_value}\n"
                        f"🔻 Error: {error_key} = {error_value}"
                    )
                    print(fail_reason)

            # if moduleName != "CINA_IPE":
            #     for dataset_type in ["positive", "negative"]:
            #         dataset_detail = overall_map.get(dataset_type)
            #         if not dataset_detail:
            #             continue
            #         # Check one key-value pair to determine if this is the right dataset type
            #         expected_key, expected_value = list(dataset_detail.items())[0]
            #         actual_value = info_dict.get(expected_key)
            #         if actual_value == expected_value:
            #             matched_dataset = True
            #             # ✅ It's a matching dataset type, now validate all keys under it
            #             print(f"[{moduleName}] {json_path}: 🔍 Detected as [{dataset_type}] dataset")
            #             for expected_key, expected_value in dataset_detail.items():
            #                 # Re-fetch for each key
            #                 actual_value = info_dict.get(expected_key)
            #                 print(f"[{moduleName}] {json_path}: 🧪 Validating [{dataset_type}] {expected_key}...")
            #                 try:
            #                     print(
            #                         f"[{moduleName}] {json_path}: ✅ PASSED - [{dataset_type}] {expected_key} = {actual_value}")
            #                     assert actual_value == expected_value, (
            #                         f"[{moduleName}] {json_path}: ❌ FAILED - [{dataset_type}] Expected {expected_key}={expected_value}, | Actual {expected_key}={actual_value}"
            #                     )
            #                 except AssertionError as e:
            #                     status = False
            #                     fail_reason = str(e)
            #                     print(fail_reason)
            #             break  # ✅ Done with validation, no need to check other type
            #     # ❌ If neither positive nor negative matched
            #     if not matched_dataset:
            #         status = False
            #         positive_map = overall_map["positive"]
            #         negative_map = overall_map["negative"]
            #
            #         positive_key, positive_value = list(positive_map.items())[0]
            #         negative_key, negative_value = list(negative_map.items())[0]
            #
            #         actual_value = info_dict.get(positive_key)
            #
            #         fail_reason = (
            #             f"[{module_name}] {json_path}: ❌ FAILED - '{positive_key} : {actual_value}' does not match either:\n"
            #             f"🔸 Positive: {positive_key} = {positive_value}\n"
            #             f"🔹 Negative: {negative_key} = {negative_value}"
            #         )
            #         print(fail_reason)
            # else:
            #     for dataset_type in ["positive", "negative", "error"]:
            #         dataset_detail = overall_map.get(dataset_type)
            #         if not dataset_detail:
            #             continue
            #         # Check one key-value pair to determine if this is the right dataset type
            #         expected_key, expected_value = list(dataset_detail.items())[0]
            #         actual_value = info_dict.get(expected_key)
            #         if actual_value == expected_value:
            #             matched_dataset = True
            #             # ✅ It's a matching dataset type, now validate all keys under it
            #             print(f"[{moduleName}] {json_path}: 🔍 Detected as [{dataset_type}] dataset")
            #             for expected_key, expected_value in dataset_detail.items():
            #                 # Re-fetch for each key
            #                 actual_value = info_dict.get(expected_key)
            #                 print(f"[{moduleName}] {json_path}: 🧪 Validating [{dataset_type}] {expected_key}...")
            #                 try:
            #                     print(
            #                         f"[{moduleName}] {json_path}: ✅ PASSED - [{dataset_type}] {expected_key} = {actual_value}")
            #                     assert actual_value == expected_value, (
            #                         f"[{moduleName}] {json_path}: ❌ FAILED - [{dataset_type}] Expected {expected_key}={expected_value}, | Actual {expected_key}={actual_value}"
            #                     )
            #                 except AssertionError as e:
            #                     status = False
            #                     fail_reason = str(e)
            #                     print(fail_reason)
            #             break  # ✅ Done with validation, no need to check other type
            #     # ❌ If neither positive nor negative matched
            #     if not matched_dataset:
            #         status = False
            #         positive_map = overall_map["positive"]
            #         negative_map = overall_map["negative"]
            #         error_map = overall_map["error"]
            #
            #         positive_key, positive_value = list(positive_map.items())[0]
            #         negative_key, negative_value = list(negative_map.items())[0]
            #         error_key, error_value = list(error_map.items())[0]
            #
            #         actual_value = info_dict.get(positive_key)
            #
            #         fail_reason = (
            #             f"[{module_name}] {json_path}: ❌ FAILED - '{positive_key} : {actual_value}' does not match either:\n"
            #             f"🔸 Positive: {positive_key} = {positive_value}\n"
            #             f"🔹 Negative: {negative_key} = {negative_value}\n"
            #             f"🔹 Error: {error_key} = {error_value}"
            #         )
            #         print(fail_reason)
        elif moduleName in anatomy_modules:
            overall_map = anatomy_modules[moduleName]
            expected_key, expected_value = list(overall_map.items())[0]
            actual_value = info_dict.get(expected_key)

            if int(actual_value) == int(expected_value):
                # print(f"[{moduleName}] {json_path}:  ✅ PASSED - processed successfully with {expected_key}:{actual_value}")
                pass
            else:
                status = False
                fail_reason = f"{moduleName}: ❌ FAILED - Expected {expected_key}={expected_value}, but got {actual_value}"
                # print(fail_reason)
        else:
            print(f"[{moduleName}] {json_path}: ℹ️ No validation rule defined.")

        results.append((moduleName, json_path, status, fail_reason, dataset_type, expected_key, actual_value))
    # print(results)

    passed = sum(1 for result in results if result[2])  # index 2 = `status`
    failed = total - passed
    elapsed = time.time() - _start_time

    print("\n=========================== test session summary ===========================")
    for module, path, ok, reason, dataset_type, expected_key, actual_value in results:
        label = f"[{module}] {path}"
        if ok:
            if module in diagnosis_modules:
                print(f"✅ {label}: PASSED")
                print(f"[{module}] {path}: 🔍 Detected as [{dataset_type}] dataset")
                print(
                    f"[{module}] {path}: ✅ PASSED - [{dataset_type}] {expected_key} = {actual_value}")
                print("\n")
            elif module in anatomy_modules:
                print(f"✅ {label}: PASSED")
                print(f"[{module}] is processed successfully with {expected_key}:{actual_value}")
                print("\n")

        else:
            print(f"❌ {label}: FAILED - {reason}")
            print("\n")
    print(".")
    print(f"\nTotal: {total} | ✅ Passed: {passed} | ❌ Failed: {failed}")

    # Add time elapsed
    elapsed = time.time() - _start_time
    print(f"🕒 Time Elapsed: {elapsed:.2f} seconds")

def print_test_summary():
    execute_all_tests()
