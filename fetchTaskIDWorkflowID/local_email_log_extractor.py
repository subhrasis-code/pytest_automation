import os
import time
import sys

def email_logs(email_root_folder, emailLogger, time_traversed, path_jobManager, email_log_file):
    print("\n")
    print(f"######### Email log file will be created for the last {time_traversed} hours #########")

    # Get the current time
    current_time = time.time()

    # Calculate the time 3 hours ago
    traversed = current_time - int(time_traversed) * 60 * 60

    # List all directories in the path
    directories = [d for d in os.listdir(email_root_folder) if os.path.isdir(os.path.join(email_root_folder, d))]

    # Filter directories created in the last traversed hours
    recent_directories = []
    for directory in directories:
        directory_path = os.path.join(email_root_folder, directory)
        creation_time = os.path.getctime(directory_path)
        if creation_time >= traversed:
            recent_directories.append(directory_path)

    # Print the recent directories
    print(f"Folders created in the last {traversed} hours:")
    with open(os.path.join(path_jobManager, emailLogger), 'w', newline='\n') as logfile:
        for directory in recent_directories:
            with open(os.path.join(directory, email_log_file), 'r') as f:
                read = f.read()
                # print(read)
                logfile.write("\n")
                logfile.write(directory)
                logfile.write(read)
                logfile.write("\n*******************************************************************************************************")
                logfile.write("\n")

if len(sys.argv) != 6:
    print("Usage: python3 emailLogger.py <email_root_folder> <emailLogger> <time_traversed> <path_jobManager>")
    sys.exit(1)
email_root_folder = sys.argv[1]
emailLogger = sys.argv[2]
time_traversed = sys.argv[3]
path_jobManager = sys.argv[4]
email_log_file = sys.argv[5]
# Search for JSON files and write data to CSV
email_logs(email_root_folder, emailLogger, time_traversed, path_jobManager, email_log_file)
