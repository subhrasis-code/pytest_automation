import pydicom
import random
import os
import csv


def get_patient_id(datasets):
    print("\n")
    print(f"######### CSV file will be created that will contain the PatientID of the datas to be pushed #########")
    current_directory = os.getcwd()
    # Get the parent directory
    parent_directory = os.path.dirname(current_directory)
    patientId_csv_path = parent_directory + "/patientId.csv"
    with open(patientId_csv_path, 'w', newline='') as csvfile:
        fieldnames = ['Dataset', "PatientID"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        x = {}
        for folder in datasets:
            file_list = []
            # Get a list of all files in the folder
            for f in os.listdir(folder):
                if os.path.isfile(os.path.join(folder,f)):
                    file_list.append(f)

            # Filter out files that don't end with ".dcm"
            dcm_files = [f for f in file_list if f.endswith(".dcm")]

            if not dcm_files:
                return f"No .dcm files exist in {folder}"  # Return None if no ".dcm" files are found

            # Choose a random ".dcm" file
            random_dcm_file = random.choice(dcm_files)
            # Join the file with the folder path
            dcm_file_path = os.path.join(folder, random_dcm_file)
            # Load the DICOM file
            ds = pydicom.dcmread(dcm_file_path)
            # Get the PatientID
            patient_id = ds.get("PatientID", "Patient ID not found")
            x = {'Dataset': folder, 'PatientID': patient_id}
            writer.writerow(x)
    print("\n")
    print(f"######### PatientID CSV file is successfully created and is present in {patientId_csv_path} #########")




# Example usage:
# dcm_file_path = "/Users/subhrasis/Documents/Rapid_pythonScripts/Performance/dataSets/sd"
# patient_id = get_patient_id(dcm_file_path)
# print("PatientID:", patient_id)