import multiprocessing
import subprocess
import glob
import time
from concurrent.futures import ThreadPoolExecutor



def push(dataset_path, IP, port):
    """Push DICOM files using dcmsend instead of storescu."""
    # Get the list of DICOM files recursively from all subdirectories
    dicom_files = glob.glob(f"{dataset_path}/**/*.dcm", recursive=True)

    if not dicom_files:
        print(f"No DICOM files found in {dataset_path}")
        return

    # # Define the dcmsend command
    # command = ["dcmsend", IP, port, "--scan-directories", "--verbose"] + dicom_files

    # Define the storescu command
    command = ["storescu", IP, port, "--scan-directories", "+r", "-v", "+sd"] + dicom_files

    time.sleep(0.2)  # Short delay before execution

    try:
        subprocess.run(command, check=True)
        print(f"✅ DICOM files successfully sent from: {dataset_path}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing dcmsend for {dataset_path}: {e}")


def push_in_3_batches(dataset_path, IP, port):
    """Push DICOM files using dcmsend in 3 separate batches."""
    # Get the list of DICOM files recursively from all subdirectories
    dicom_files = glob.glob(f"{dataset_path}/**/*.dcm", recursive=True)

    if not dicom_files:
        print(f"No DICOM files found in {dataset_path}")
        return

    # Define batch size
    batch_size = len(dicom_files) // 3
    if batch_size == 0:
        batch_size = len(dicom_files)  # If less than 3 files, send all in one batch

    # Split files into 3 batches
    batch_1 = dicom_files[:batch_size]
    batch_2 = dicom_files[batch_size: 2 * batch_size]
    batch_3 = dicom_files[2 * batch_size:]

    batches = [batch_1, batch_2, batch_3]

    # Push each batch with a separate association
    for i, batch in enumerate(batches, start=1):
        if not batch:
            continue  # Skip empty batches

        print(f"\n🚀 Pushing Batch {i} with {len(batch)} files...")
        command = ["dcmsend", IP, str(port), "--scan-directories", "--verbose"] + batch
        time.sleep(0.2)  # Short delay before execution

        try:
            subprocess.run(command, check=True)
            print(f"✅ Batch {i} successfully sent.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error executing dcmsend for Batch {i}: {e}")


# def push_in_2batches(dataset_path, IP, port):
#     print("Delay Push. push_in_2batches")
#
#     # Get the list of DICOM files in the directory
#     dicom_files = glob.glob(f"{dataset_path}/*.dcm")
#
#     # Initialize the maximum files to push in the first batch
#     max_files_per_batch = 25
#
#     # Create the initial command base
#     command_base = ["storescu", IP, str(port), "-r", "-v"]
#
#
#     # Push the first 25 images
#     first_batch = dicom_files[:max_files_per_batch]
#     command_first_batch = command_base + first_batch
#
#     try:
#         subprocess.run(command_first_batch, check=True)
#         print("Command executed successfully for batch 1")
#     except subprocess.CalledProcessError as e:
#         print(f"Error executing command for batch 1: {e}")
#         return
#
#     # Introduce a delay after the first batch of 25 images
#     print("Pausing for 10 seconds after pushing 25 images...")
#     time.sleep(10)
#
#     # Push all the remaining images at once within the same association
#     remaining_files = dicom_files[max_files_per_batch:]
#     if remaining_files:
#         command_remaining = command_base + remaining_files
#         try:
#             subprocess.run(command_remaining, check=True)
#             print("Command executed successfully for remaining images")
#         except subprocess.CalledProcessError as e:
#             print(f"Error executing command for remaining images: {e}")


# Test case (C49071) delay
def push_C49071(dataset_path, IP, port):
    print("Starting Push with Delays")
    dicom_files = glob.glob(f"{dataset_path}/*.dcm")
    if not dicom_files:
        print("No DICOM files found in the specified directory.")
        return

    image_counter = 0
    max_files_per_batch = 25

    def execute_command(files):
        command = ["storescu", IP, port] + files + ["+sd", "-r", "--scan-directories", "+r", "-v", "+sd"]
        try:
            subprocess.run(command, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {e}")
            return False

    print("Establishing initial association...")
    if not execute_command(dicom_files[:1]):
        print("Failed to establish initial association.")
        return
    print("Initial association established. Waiting for 29 seconds...")
    time.sleep(29)

    # Push the first 25 images with a 31-second delay after the first batch
    while image_counter < min(len(dicom_files), max_files_per_batch):
        end_index = min(image_counter + max_files_per_batch, len(dicom_files))
        current_batch = dicom_files[image_counter:end_index]

        if not execute_command(current_batch):
            print("Association timed out or failed. Re-establishing association...")
            if not execute_command(dicom_files[:1]):
                print("Failed to re-establish association.")
                return

        image_counter += max_files_per_batch

        if image_counter == 25:
            print("Pausing for 20 seconds after the first 25 images...")
            time.sleep(31)

    # Push the remaining images without any delay
    while image_counter < len(dicom_files):
        current_batch = dicom_files[image_counter:]

        if not execute_command(current_batch):
            print("Association timed out or failed. Re-establishing association...")
            if not execute_command(dicom_files[:1]):
                print("Failed to re-establish association.")
                return

        break


def push_executor(IP, port, datasets, parallel_push):
    if parallel_push == "True":
        print("parallel data push : True")
        # Create a ThreadPoolExecutor with max_workers set to the number of dataset paths
        with ThreadPoolExecutor(max_workers=len(datasets)) as executor:
            time.sleep(0.15)
            # Submit push function for each dataset path
            for dataset_path_tuple in zip(datasets):
                dataset_path = str(dataset_path_tuple[0])
                executor.submit(push, dataset_path, IP, port)

                # push with delay
                # executor.submit(push_with_delay_introduced, dataset_path, IP, port)

                # push in 2 batches
                # executor.submit(push_in_3_batches, dataset_path, IP, port)
    else:
        print("parallel data push : False")
        # Iterate over each dataset path and call push sequentially
        time.sleep(0.15)
        for dataset_path in datasets:
            dataset_path_str = str(dataset_path)
            push(dataset_path_str, IP, port)

            # push with delay
            # push_with_delay_introduced(dataset_path_str, IP, port)

            # testcase
            # push_C49071(dataset_path_str, IP, port)