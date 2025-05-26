import multiprocessing
import subprocess
import glob
import time
import logging
import sys
from concurrent.futures import ThreadPoolExecutor

# Logger setup
logger = logging.getLogger("push_datasets")
logger.setLevel(logging.DEBUG)  # Capture all logs DEBUG and above

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)



def push_single_association(dataset_path, IP, port):
    logger.info("Starting to push via Single Association \n")
    # Get the list of DICOM files recursively from all subdirectories
    dicom_files = glob.glob(f"{dataset_path}/**/*.dcm", recursive=True)

    if not dicom_files:
        logger.error(f"❌ No DICOM files found in {dataset_path}")
        return

    # Define the storescu command
    command = ["storescu", IP, port, "-v"] + dicom_files

    time.sleep(0.2)  # Short delay before execution

    try:
        subprocess.run(command, check=True)
        logger.info(f"✅ DICOM files successfully sent from: {dataset_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error executing storescu for {dataset_path}: {e}")

def push_multi_associations(dataset_path, IP, port, batch_count, batch_delay):
    """Push DICOM files using multiple associations."""
    logger.info("Starting to push via Multi Associations \n")
    # Get the list of DICOM files recursively from all subdirectories
    dicom_files = glob.glob(f"{dataset_path}/**/*.dcm", recursive=True)

    if not dicom_files:
        logger.error(f"❌ No DICOM files found in {dataset_path}")
        return

    total_files = len(dicom_files)
    if batch_count > total_files:
        logger.warning(f"Warning: batch_count ({batch_count}) is greater than total_files ({total_files}).")
        logger.debug("🔁 Reducing batch_count to match the number of files.")
        batch_count = total_files # One file per batch

    # Define batch size
    batch_size = total_files // batch_count
    if batch_size == 0:
        batch_size = total_files  # If files are very few, send all in one batch

    # Split files into batches
    batches = []
    for i in range(batch_count):
        start_index = i * batch_size
        end_index = (i + 1) * batch_size
        batches.append(dicom_files[start_index:end_index])

    # In case some files are left (due to integer division), add them to the last batch
    if total_files > batch_count * batch_size:
        batches[-1].extend(dicom_files[batch_count * batch_size:])

    # Push each batch with a separate association
    for i, batch in enumerate(batches, start=1):
        if not batch:
            logger.warning(f"⚠️ Batch {i} is empty. Skipping...")
            continue  # Skip empty batches

        logger.info(f"\n🚀 Pushing Batch {i} with {len(batch)} files...")

        # command = ["storescu", IP, port, "--scan-directories", "+r", "-v", "+sd"] + batch
        command = ["storescu", IP, port, "-v"] + batch
        time.sleep(0.2)  # Short delay before execution

        try:
            subprocess.run(command, check=True)
            logger.info(f"✅ Batch {i} successfully sent.")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Batch {i} failed to send. Error: {e}")
            logger.debug(f"🔄 Continuing with next batch...")
        # Sleep only if not the last batch
        if i != len(batches):
            time.sleep(batch_delay)

    logger.info("\n🎯 All batches attempted. Task finished!")

def push_executor(IP, port, datasets, parallel_push, multi_associations=False, batch_count=2, batch_delay=25):
    if parallel_push == "True":
        logger.info("parallel data push : True")
        # Create a ThreadPoolExecutor with max_workers set to the number of dataset paths
        with ThreadPoolExecutor(max_workers=len(datasets)) as executor:
            time.sleep(0.15)
            # Submit push function for each dataset path
            for dataset_path_tuple in zip(datasets):
                dataset_path = str(dataset_path_tuple[0]).strip()
                # executor.submit(push_single_association(), dataset_path, IP, port)
                executor.submit(push_single_association, dataset_path, IP, port)

    else:
        logger.info("parallel data push : False")
        # Iterate over each dataset path and call push sequentially
        time.sleep(0.15)
        for dataset_path in datasets:
            dataset_path_str = str(dataset_path).strip()
            if multi_associations == "True":
                if batch_count >= 2:
                    push_multi_associations(dataset_path_str, IP, port, batch_count, batch_delay)
                else:
                    logger.warning(f"⚠️  batch_count is {batch_count}, must be >= 2 when using multi_associations. Falling back to single association push.")
                    push_single_association(dataset_path_str, IP, port)
            else:
                push_single_association(dataset_path_str, IP, port)

