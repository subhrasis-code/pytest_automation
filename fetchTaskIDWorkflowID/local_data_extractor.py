import os
import json
import csv
import time
import sys
import glob
import subprocess

def check_png_jpg(result_directory):
    # Check if the directory exists
    if os.path.exists(result_directory):
        if "/neuro3d/" in result_directory:
            folder = os.path.join(result_directory, 'mip_a_p_rot_vessel_view')
        elif "/ANRTN/" in result_directory:
            folder = os.path.join(result_directory, 'OutputImages')
        else:
            folder = result_directory
        # Check for PNG files
        png_files = glob.glob(os.path.join(folder, '*.png'))
        # Check for JPG files
        jpg_files = glob.glob(os.path.join(folder, '*.jpg'))
        if png_files:
            PNG = True
        else:
            PNG = False
        if jpg_files:
            JPG = True
        else:
            JPG = False

        return PNG, JPG
    else:
        print(f"The directory {result_directory} does not exist.")
        return False, False


def search_output_json(root_folder, output_csv, time_traversed, site_name):
    print("\n")
    print(f"######### CSV file will be created for the last {time_traversed} hours #########")
    with open(output_csv, 'w', newline='') as csvfile:
        fieldnames = ['OnPremResultsDir', 'WorkflowID', 'corelationID', 'ResultFile_JM', "PatientID", "ReturnCodeDescription"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        current_time = time.time()
        traversed = current_time - int(time_traversed) * 60 * 60
        for root, dirs, files in os.walk(root_folder):
            x = {}
            for file in files:
                if file == "workflow_input.json":
                    workflow_input_file_path = os.path.join(root, file)
                    file_creation_time = os.path.getctime(workflow_input_file_path)
                    if file_creation_time >= traversed:
                        with open(workflow_input_file_path, 'r') as f:
                            data = json.load(f)
                            if "workflowID" in data:
                                WorkflowID = data['workflowID']
                                corelationID = data['corelationID']
                                OnPremResultsDir = data['input']['rapid_cloud_connector_task']['OnPremResultsDir']

                                # printing the datas wrt the required site name
                                if site_name in OnPremResultsDir:
                                    PNG, JPG = check_png_jpg(os.path.join(OnPremResultsDir, 'results'))
                                    if PNG == True and JPG == True:
                                        x = {'OnPremResultsDir': OnPremResultsDir, 'WorkflowID': WorkflowID, "corelationID": corelationID, 'ResultFile_JM': True}
                                    else:
                                        x = {'OnPremResultsDir': OnPremResultsDir, 'WorkflowID': WorkflowID, "corelationID": corelationID, 'ResultFile_JM': False}
                                    # here we are checking about "output.json" file because we are confirmed that this file is created within the traveresed time
                                    if "output.json" in files:
                                        output_json_file_path = os.path.join(root, "output.json")
                                        with open(output_json_file_path, 'r') as fo:
                                            output_data = json.load(fo)

                                            def checkPatientID():
                                                # Run grep command to search for PatientID in the JSON file
                                                grep_command = f"grep -q 'PatientID' {output_json_file_path}"
                                                grep_process = subprocess.run(grep_command, shell=True, check=False)
                                                # Check the return code of grep
                                                if grep_process.returncode == 0:
                                                    # If grep exits with 0, PatientID is found
                                                    PatientID = output_data['DICOMHeaderInfo']['Patient']['PatientID']
                                                #
                                                else:
                                                    # If grep returns a non-zero exit code, PatientID is not found
                                                    PatientID = "Not Found"
                                                return PatientID

                                            def checkReturnCodeDescription():
                                                pass
                                                # Run grep command to search for PatientID in the JSON file
                                                grep_command = f"grep -q 'ReturnCodeDescription' {output_json_file_path}"
                                                grep_process = subprocess.run(grep_command, shell=True, check=False)
                                                # Check the return code of grep
                                                if grep_process.returncode == 0:
                                                    # If grep exits with 0, ReturnCodeDescription is found
                                                    ReturnCodeDescription = output_data["ReturnCodeDescription"]
                                                else:
                                                    # If grep returns a non-zero exit code, PatientID is not found
                                                    ReturnCodeDescription = "Not Found"
                                                return ReturnCodeDescription

                                            PatientID = checkPatientID()
                                            ReturnCodeDescription = checkReturnCodeDescription()
                                            x["PatientID"] = PatientID
                                            x["ReturnCodeDescription"] = ReturnCodeDescription
                                    else:
                                        x["PatientID"] = "output.json file does'nt exist"
                                        x["ReturnCodeDescription"] = "output.json file does'nt exist"
                                    writer.writerow(x)
                            else:
                                x["WorkflowID"] = f"{data['workflowID']} does'nt exist."



if len(sys.argv) != 5:
    print("Usage: python3 data_extractor.py <root_folder> <output_csv> <time_traversed>")
    sys.exit(1)
root_folder = sys.argv[1]
output_csv = sys.argv[2]
time_traversed = sys.argv[3]
site_name = sys.argv[4]

# Search for JSON files and write data to CSV
search_output_json(root_folder, output_csv, time_traversed, site_name)
