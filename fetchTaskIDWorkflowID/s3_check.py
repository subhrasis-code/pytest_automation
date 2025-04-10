import csv
import boto3
import logging
import time


# bucket_name, s3_server_name will come from .json file

def checker(bucket, site_name, s3_server_name, s3_module_name, s3_taskId, jsonFileName):
    object_found = False
    for obj in bucket.objects.filter(Prefix=f"{s3_server_name}/{site_name}/{s3_module_name}/{s3_taskId}/{jsonFileName}"):
    # for obj in bucket.objects.filter(Prefix="duck_system/site1/hemorrhage/1350/outputjson.json"):
        object_found = True
        # print(f"\tFolder: {obj.key}")
        break  # Stop searching once the object is found

    if object_found:
        # print(f"{jsonFileName} exists in the s3 bucket for {s3_module_name} module.")
        return True
    else:
        print(f"WARNING: {s3_server_name}/{site_name}/{s3_module_name}/{s3_taskId}/{jsonFileName} NOT Exist.")
        return False


def get_s3_module_name(module):
    try:
        if module == "PETN":
            s3_module_name = "CTPA"
            filename = "outputjson.json"
        elif module == "RVLV":
            s3_module_name = "RVLV"
            filename = "outputjson.json"
        elif module == "Mismatch":
            s3_module_name = "Mismatch"
            filename = "outputjson.json"
        elif module == "ANRTN":
            s3_module_name = "ANRTN"
            filename = "outputjson.json"
        elif module == "hemorrhage":
            s3_module_name = "hemorrhage"
            filename = "outputjson.json"
        elif module == "Hyperdensity":
            s3_module_name = "Hyperdensity"
            filename = "outputjson.json"
        elif module == "Hypodensity":
            s3_module_name = "Hypodensity"
            filename = "outputjson.json"
        elif module in {"NCCTStroke", "NCCT"}:
            s3_module_name = "LVO_ON_NCCT"
            filename = "outputjson.json"
        elif module == "Octopus":
            s3_module_name = "ASPECTS"
            filename = "outputjson.json"
        elif module == "angio":
            s3_module_name = "CTA"
            filename = "outputjson.json"
        elif module == "neuro3d":
            s3_module_name = "NEURO3D"
            filename = "output.json"
        elif module == "sdh":
            s3_module_name = "SDH"
            filename = "output.json"

        return s3_module_name, filename
    except:
        return f"Invalid module name {module}"

def s3executor(OnPremResultsDir, bucket, site_name, s3_server_name):
    try:
        parts = OnPremResultsDir.split('/')
        # Ensure the path has enough parts
        if len(parts) < 5:
            raise ValueError("OnPremResultsDir does not have enough parts to extract required elements.")

        print("&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&& : ", OnPremResultsDir, bucket, site_name, s3_server_name,
              "&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&&")
        # Extract the desired elements based on their positions
        s3_module_name, jsonFileName = get_s3_module_name(str(parts[-2]))
        s3_taskId = parts[-1].split('_')[0]

        # Check if the extracted values are valid
        if not s3_module_name or not jsonFileName:
            raise ValueError("Failed to extract s3_module_name or jsonFileName from the path.")

        result = checker(bucket, site_name, s3_server_name, s3_module_name, s3_taskId, jsonFileName)
        return result

    except ValueError as ve:
        print(f"ValueError occurred: {ve}")
        return None
    except IndexError as ie:
        print(f"IndexError occurred: {ie}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

    # def s3executor(OnPremResultsDir, bucket, site_name, s3_server_name):
    #     parts = OnPremResultsDir.split('/')
    #     # Extract the desired elements based on their positions
    #     if len(parts) >= 5:
    #         s3_module_name, jsonFileName = get_s3_module_name(str(parts[-2]))
    #         s3_taskId = parts[-1].split('_')[0]
    #         result = checker(bucket, site_name, s3_server_name, s3_module_name, s3_taskId, jsonFileName)
    #         return result

# bucket_name = "ischemaview-qa-us-west-2"
# s3executor(bucket_name, "site1", "duck_system")