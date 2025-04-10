import os
import json
import csv

def search_output_json(root_folder):
    data_rows = []
    for root, dirs, files in os.walk(root_folder):
        for file in files:
            if file == "README":
                print(root)
                output_file_path = os.path.join(root, file)
                print(output_file_path)

# Specify the root folder
root_folder = "/Users/subhrasis/Documents/Rapid_pythonScripts/Automation_no_global"

# Search for JSON files and collect data
data_rows = search_output_json(root_folder)