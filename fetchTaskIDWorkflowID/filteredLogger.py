import csv
import os

# Get the directory where the script is located
script_directory = os.path.dirname(os.path.abspath(__file__))
current_directory = script_directory
# print(current_directory)

# Get the parent directory
# parent_directory = os.path.dirname(current_directory)
# patientId_csv_path = parent_directory + "/patientId.csv"

# Creating a log file that will have only the logs wrt to the patientIDs pushed in the latest run
# Create the logger directory if it doesn't exist
logger_directory = os.path.join(current_directory, "logger")
if not os.path.exists(logger_directory):
    os.makedirs(logger_directory)

# Define the log file path
pushedPatientIDLogger_path = os.path.join(logger_directory, "pushedPatientIDLogger.log")
# pushedPatientIDLogger_path = current_directory + "/pushedPatientIDLogger.log"
logger_path = os.path.join(logger_directory, "logger.log")
patientId_csv_path = os.path.join(logger_directory, "patientId.csv")

def logger_patientId():
    # Check if the source file exists
    if os.path.exists(patientId_csv_path):
        # This file is the file in which the filtered logs will be printed
        with open(pushedPatientIDLogger_path, 'w') as p_log:
            # this file is the mail logger file that cointains the logs since the given traversed time
            with open(logger_path, 'r') as logfile:
                # list of lines present in logger.log file
                log_reader = logfile.readlines()
                # This file contains the PatientID(s) of the datasets that we had pushed when we ran UploadDataset script
                with open(patientId_csv_path, newline='') as csvfile:
                    # Create a CSV reader object
                    reader = csv.reader(csvfile)
                    # Skip the header row
                    next(reader)
                    # Iterate over each row in the CSV file
                    for row in reader:
                        # Extract PatientID (assuming it's the second column)
                        patientID = row[1]
                        for logline in log_reader:
                            if f"PatientId: {patientID}" in logline:
                                # write the above filtered logline into pushedPatientIDLogger.log
                                p_log.write(logline)

# logger_patientId()