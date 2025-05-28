import subprocess
import json
import os
import time
from datetime import datetime
import logging
import sys
# from logger_config import get_logger

# Logger setup
logger = logging.getLogger("check_outputjson")
logger.setLevel(logging.DEBUG)  # Capture all logs DEBUG and above

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


# Keys to look for
keys_to_extract = ["ReturnCodeDescription", "returnCodeDescription", "ReturnCode", "ProcessingTimeInSeconds", "ProcessingTimeSeconds",
                   "processingTimeInSeconds", "NumberOfSlices", "NumberOfSlicesAffected", "RVLVRatio", "ich_version", "HemorrhageDetected",
                   "scoreLeftHemisphere", "scoreRightHemisphere", "aspects_version", "Region", "NCCTStrokeLVOSuspected", "AneurysmSuspected",
                   "valueString", "scanCaution", "scanRejected", "LVODetectionEnabled", "LVODetected", "USAVersionLimitation", "VesselDensityRatio",
                   "Description", "ModuleName", "moduleName", "ArtifactsDetected", "NCCTArtifactsJSONFilename", "SDHSuspected", "PatientName",
                   "PatientAge", "SeriesDescription", "SeriesInstanceUID", "StudyInstanceUID"
                   ]


diagnosis_modules = {
    "Rapid PE": {
        "positive": {"Description": "Suspected PE"},
        "negative": {"Description": "CTPA processed.\nPlease review source images."},
        "ProcessingTimeInSeconds": 300
    },
    "ICH": {
        "positive": {"HemorrhageDetected": "True"},
        "negative": {"HemorrhageDetected": "False"},
        "ProcessingTimeInSeconds": 200
    },
    "SDH": {
        "positive": {"SDHSuspected": "True"},
        "negative": {"SDHSuspected": "False"},
        "ProcessingTimeInSeconds": 78
    },
    "NCCT Stroke": {
        "positive": {"NCCTStrokeLVOSuspected": "True"},
        "negative": {"NCCTStrokeLVOSuspected": "False"},
        "ProcessingTimeInSeconds": 300
    },
    "CINA_IPE": {
        "positive": {"valueString": "SUSPECTED"},
        "negative": {"valueString": "PROCESSED"},
        "error": {"returnCodeDescription": "Input DICOM data invalid"},
        "ProcessingTimeInSeconds": 300
    },
    "ANRTN": {
        "positive": {"AneurysmSuspected": "True"},
        "negative": {"AneurysmSuspected": "False"},
        "ProcessingTimeInSeconds": 599
    },
    "CTA": {
        "positive": {"LVODetected": "True"},
        "negative": {"LVODetected": "False"},
        "ProcessingTimeInSeconds": 480
    },
    "LVO": {
        "positive": {"LVODetected": "True"},
        "negative": {"LVODetected": "False"},
        "ProcessingTimeInSeconds": 480
    },
    "CTA/LVO": {
        "positive": {"LVODetected": "True"},
        "negative": {"LVODetected": "False"},
        "ProcessingTimeInSeconds": 480
    }
}


anatomy_modules = {
    "Rapid RV/LV": {
        "ReturnCode": 0,
        "ProcessingTimeInSeconds": 300
    },
    "Rapid Hyperdensity": {
        "ReturnCode": 0,
        "ProcessingTimeInSeconds": 89
    },
    "Hypodensity": {
        "ReturnCode": 0,
        "ProcessingTimeInSeconds": 219
    },
    "RAPIDNEURO3D": {
        "ReturnCode": 0,
        "ProcessingTimeInSeconds": 360
    },
    "ASPECTS1": {
        "ReturnCode": 0,
        "ProcessingTimeInSeconds": 545
    },
    "ASPECTS3": {
        "ReturnCode": 0,
        "ProcessingTimeInSeconds": 120
    },
    "Mismatch": {
        "ReturnCode": 0,
        "ProcessingTimeInSeconds": 100
    }
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
        logger.error(f"Error reading {json_path}: {result.stderr.strip()}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {json_path}: {e}")
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


def find_all_keys_recursive(json_data):
    """
    Recursively search for all occurrences of target keys in a nested dictionary/list.
    Returns 3 separate lists: SeriesDescriptions, SeriesInstanceUIDs, StudyInstanceUIDs.
    """
    result_series_descriptions_list = []
    result_series_instance_uids_list = []
    result_study_instance_uids_list = []

    def _recursive_search(data):
        # Check if the current level of data is a dictionary
        if isinstance(data, dict):
            for key, value in data.items():
                # If the key is "SeriesDescription", append its value to the corresponding list
                if key == "SeriesDescription":
                    result_series_descriptions_list.append(value)
                # If the key is "SeriesInstanceUID", append its value to the corresponding list
                elif key == "SeriesInstanceUID":
                    result_series_instance_uids_list.append(value)
                # If the key is "StudyInstanceUID", append its value to the corresponding list
                elif key == "StudyInstanceUID":
                    result_study_instance_uids_list.append(value)

                # Recursively call the function to go deeper into nested structures
                _recursive_search(value)

        # If the current level is a list, iterate through each item
        elif isinstance(data, list):
            for item in data:
                # Recursively call the function for each item in the list
                _recursive_search(item)

    # Start the recursive search on the input JSON data
    _recursive_search(json_data)

    return (
        result_series_descriptions_list,
        result_series_instance_uids_list,
        result_study_instance_uids_list
    )


def check_outputjson_executor(json_path, kubeconfig_path, pod_name, namespace, module_name):
    if json_path not in _printed_paths:
        # print(f"📄 output.json created: {json_path}")
        logger.info(f"📄 output.json created: {json_path}")
        _printed_paths.add(json_path)
        case_name = os.path.basename(os.path.dirname(json_path))
        _pending_tests.append((module_name, case_name, json_path, kubeconfig_path, pod_name, namespace))
        # print("Going out of check_outputjson_executor method")

def compare_patient_name(patient_name, source_patinet_names):
    try:
        return patient_name in source_patinet_names
    except Exception as e:
        logger.error(f"Error comparing patient names: {e}")
        return False

def execute_all_tests(source_series_descs, source_series_uids, source_study_uids, source_patinet_names):
    total = len(_pending_tests)
    logger.info("\n============================= test session starts =============================")
    logger.info(f"collected {total} items")

    results = []

    for idx, (module_name, case_name, json_path, kubeconfig_path, pod_name, namespace) in enumerate(_pending_tests, 1):
        progress = int((idx / total) * 100)
        logger.info(f"\nValidation for output.json::[{module_name}_{case_name}] PASSED [{progress}%]")

        json_data = read_json_from_pod(json_path, kubeconfig_path, pod_name, namespace)
        if not json_data:
            results.append((module_name, json_path, False, "Failed to read or parse JSON"))
            continue

        extracted_values = []
        for key in keys_to_extract:
            if key not in ["SeriesDescription", "SeriesInstanceUID", "StudyInstanceUID"]:
                value = find_key_recursive(json_data, key)
                if value is None:
                    continue  # Skip if value is None
                extracted_values.append(f"{key}: {value}")
                # if isinstance(value, dict):
                #     extracted_values.append(f"{key}: {value}")
                # else:
                #     extracted_values.append(f"{key}: {value}")
        res_series_descs, res_series_uids, res_study_uids = find_all_keys_recursive(json_data)

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
            logger.warning("⚠️ Failed to write log:", e)

        status = True
        fail_reason = ""
        dataset_type = None
        expected_key = None
        actual_value = None
        possible_module_name_keys = ["ModuleName", "moduleName", "modulename"]
        moduleName = next((info_dict.get(key) for key in possible_module_name_keys if info_dict.get(key)), "UnknownModule")
        num_slices = info_dict.get("NumberOfSlices") or info_dict.get("NumberofSlices")
        patient_name = info_dict.get("PatientName")
        patient_age = info_dict.get("PatientAge")
        pt_within_limit = False  # Default value
        threshold = None
        actual_pt = None
        patient_name_match = compare_patient_name(patient_name, source_patinet_names)

        raw_pt = (
                info_dict.get("ProcessingTimeInSeconds") or
                info_dict.get("ProcessingTimeSeconds") or
                info_dict.get("processingTimeInSeconds")
        )
        try:
            actual_pt = round(float(raw_pt), 2)
        except (ValueError, TypeError):
            actual_pt = None  # or handle the error appropriately

        def pt_validator(actual_pt_val, threshold_val):
            # print("Inside pt_validator")
            if actual_pt_val is not None and threshold_val is not None:
                if actual_pt_val <= threshold_val:
                    return True
                else:
                    return False
            else:
                return False

        if moduleName in diagnosis_modules:
            overall_map = diagnosis_modules[moduleName]
            matched_dataset = False

            # raw_pt = (
            #         info_dict.get("ProcessingTimeInSeconds") or
            #         info_dict.get("ProcessingTimeSeconds") or
            #         info_dict.get("processingTimeInSeconds")
            # )
            # try:
            #     actual_pt = float(raw_pt)
            # except (ValueError, TypeError):
            #     actual_pt = None  # or handle the error appropriately

            def diagnosis_threshold_calc(moduleName, num_slices):
                threshold = None
                pt_status_local = True #  Indicates whether the threshold was successfully calculated (e.g. valid slice count, key present, etc.)
                pt_error_local = ""
                if moduleName == "ICH":
                    if num_slices is not None:
                        try:
                            num_slices = int(num_slices)
                            threshold = num_slices * 5
                        except ValueError:
                            pt_status_local = False
                            pt_error_local = f"[{moduleName}] {json_path}: ❌ FAILED - Invalid NumberOfSlices: {num_slices}"
                            # summary_messages.append(pt_error_local)
                            # threshold = None
                    else:
                        pt_status_local = False
                        pt_error_local = f"[{moduleName}] {json_path}: ❌ FAILED - NumberOfSlices key not found"
                else:
                    threshold = (
                            overall_map.get("ProcessingTimeInSeconds")
                            or overall_map.get("ProcessingTimeSeconds")
                            or overall_map.get("processingTimeInSeconds")
                    )
                return float(threshold) if threshold is not None else None, pt_status_local, pt_error_local


            def validate_dataset_type(moduleName, json_path, info_dict, dataset_types, overall_map):
                for dataset_type in dataset_types:
                    dataset_detail = overall_map.get(dataset_type)
                    if not dataset_detail:
                        continue
                    # Check one key-value pair to determine if this is the right dataset type
                    expected_key, expected_value = list(dataset_detail.items())[0]
                    actual_value = info_dict.get(expected_key)

                    if str(actual_value).lower() == str(expected_value).lower():
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
                        return True, dataset_type, expected_key, actual_value  # ✅ Matching dataset found
                return False, None, None, None  # ❌ No match

            if moduleName != "CINA_IPE":
                matched_dataset, dataset_type, expected_key, actual_value = validate_dataset_type(moduleName, json_path, info_dict, ["positive", "negative"], overall_map)
                threshold, pt_status_local, pt_error_local = diagnosis_threshold_calc(moduleName, num_slices)
                if pt_status_local:
                    # print("inside pt_status_local:")
                    pt_within_limit = pt_validator(actual_pt, threshold)
                else:
                    logger.error(pt_error_local)
                # print("pt_within_limit: ", pt_within_limit)
                # print("threshold: ", threshold)
                # print("actual_pt: ", actual_pt)

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
                    logger.error(fail_reason)

            # elif moduleName == "ICH":
                # matched_dataset = validate_dataset_type(moduleName, json_path, info_dict, ["positive", "negative", "ncctArtifactDetection_positive", "ncctArtifactDetection_negative"], overall_map)

            else:  # For CINA_IPE
                matched_dataset, dataset_type, expected_key, actual_value = validate_dataset_type(moduleName, json_path, info_dict, ["positive", "negative", "error"], overall_map)
                threshold, pt_status_local, pt_error_local = diagnosis_threshold_calc(moduleName, num_slices)
                if pt_status_local:
                    pt_within_limit = pt_validator(actual_pt, threshold)
                else:
                    print(pt_error_local)
                # print("pt_within_limit: ", pt_within_limit)
                # print("threshold: ", threshold)
                # print("actual_pt: ", actual_pt)

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
                        logger.error(fail_reason)

        elif moduleName in anatomy_modules:
            overall_map = anatomy_modules[moduleName]
            expected_key, expected_value = list(overall_map.items())[0]
            actual_value = info_dict.get(expected_key)

            def anatomy_threshold_calc(moduleName, num_slices):
                # print("inside anatomy_threshold_calc")
                threshold = None
                pt_status_local = True
                pt_error_local = ""
                if moduleName == "RAPIDNEURO3D":
                    if num_slices is not None:
                        try:
                            num_slices = int(num_slices)
                            threshold = round(num_slices * 0.64, 2) # 0.64 seconds per slice
                        except ValueError:
                            pt_status_local = False
                            pt_error_local = f"[{moduleName}] {json_path}: ❌ FAILED - Invalid NumberOfSlices: {num_slices}"
                            # summary_messages.append(pt_error_local)
                            # threshold = None
                    else:
                        pt_status_local = False
                        pt_error_local = f"[{moduleName}] {json_path}: ❌ FAILED - NumberOfSlices key not found"
                elif moduleName == "Mismatch":
                    if num_slices is not None:
                        try:
                            num_slices = int(num_slices)
                            threshold = num_slices * 5
                        except ValueError:
                            pt_status_local = False
                            pt_error_local = f"[{moduleName}] {json_path}: ❌ FAILED - Invalid NumberOfSlices: {num_slices}"
                            # summary_messages.append(pt_error_local)
                            # threshold = None
                    else:
                        pt_status_local = False
                        pt_error_local = f"[{moduleName}] {json_path}: ❌ FAILED - NumberOfSlices key not found"
                else:
                    threshold = (
                            overall_map.get("ProcessingTimeInSeconds")
                            or overall_map.get("ProcessingTimeSeconds")
                            or overall_map.get("processingTimeInSeconds")
                    )
                return float(threshold) if threshold is not None else None, pt_status_local, pt_error_local

            threshold, pt_status_local, pt_error_local = anatomy_threshold_calc(moduleName, num_slices)
            if pt_status_local:
                # print("inside pt_status_local:")
                pt_within_limit = pt_validator(actual_pt, threshold)
            else:
                print(pt_error_local)
            # print("pt_within_limit: ", pt_within_limit)
            # print("threshold: ", threshold)
            # print("actual_pt: ", actual_pt)

            if int(actual_value) == int(expected_value):
                # print(f"[{moduleName}] {json_path}:  ✅ PASSED - processed successfully with {expected_key}:{actual_value}")
                pass
            else:
                status = False
                fail_reason = f"{moduleName}: ❌ FAILED - Expected {expected_key}={expected_value}, but got {actual_value}"
                # print(fail_reason)
        else:
            logger.info(f"[{moduleName}] {json_path}: ℹ️ No validation rule defined.")


        results.append((moduleName, json_path, status, fail_reason, dataset_type, expected_key, actual_value, pt_within_limit,
                        num_slices, actual_pt, threshold, patient_name, patient_age, patient_name_match,
                        res_series_descs, res_series_uids, res_study_uids))
    # print(results)

    passed = sum(1 for result in results if result[2])  # index 2 = `status`
    failed = total - passed
    elapsed = time.time() - _start_time

    logger.info("\n=========================== test session summary ===========================")

    def summarize_pt_verdict(pt_within_limit, num_slices, actual_processing_time, threshold):
        if pt_within_limit:
            return f" ✅ PASSED - Number of slices: {num_slices}, Processing time: {actual_processing_time} seconds <= Threshold: {threshold} seconds "
        else:
            return f" ❌ Failed - Number of slices: {num_slices}, Processing time: {actual_processing_time} seconds > Threshold: {threshold} seconds "

    for (module, path, ok, reason, dataset_type, expected_key, actual_value, pt_within_limit, num_slices,
         actual_processing_time,
         threshold, patient_name, patient_age, patient_name_match, res_series_descs, res_series_uids,
         res_study_uids) in results:

        label = f"[{module}] {path}"
        common_info = (
            f"PatientName : {patient_name}, PatientAge : {patient_age}\n"
            f"SeriesDescription : {res_series_descs}\n"
            f"SeriesInstanceUID : {res_series_uids}\n"
            f"StudyInstanceUID : {res_study_uids}"
        )

        if ok:
            logger.info(f"✅ {label}: PASSED")
            logger.info(common_info)

            if module in diagnosis_modules:
                logger.info(f"{label}: 🔍 Detected as [{dataset_type}] dataset")
                logger.info(f"{label}: ✅ PASSED - [{dataset_type}] {expected_key} = {actual_value}")

            elif module in anatomy_modules:
                logger.info(f"[{module}] is processed successfully with {expected_key}:{actual_value}")

        else:
            logger.error(f"❌ {label}: FAILED - {reason}")
            logger.info(common_info)

        # Patient name match status
        match_patient_name_msg = "✅ Result PatientName matches with source PatientName" if patient_name_match \
            else "❌ Result PatientName does'nt matche with source PatientName"
        logger.info(match_patient_name_msg)

        # Processing time verdict
        pt_verdict = summarize_pt_verdict(pt_within_limit, str(num_slices), str(actual_processing_time), str(threshold))
        logger.info(f"{label}:{pt_verdict}")
        print("\n")
    logger.info(".")
    logger.debug(f"\nTotal: {total} | ✅ Passed: {passed} | ❌ Failed: {failed}")

    # Add time elapsed
    elapsed = time.time() - _start_time
    logger.info(f"🕒 Time Elapsed: {elapsed:.2f} seconds")

def print_test_summary(series_descriptions_list, series_instance_uids_list, study_instance_uids_list, source_patinet_names):
    execute_all_tests(series_descriptions_list, series_instance_uids_list, study_instance_uids_list, source_patinet_names)