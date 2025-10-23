import multiprocessing
import subprocess
import glob
import time
import logging
import sys
import random
import pydicom
from concurrent.futures import ThreadPoolExecutor

# Logger setup
logger = logging.getLogger("push_datasets")
logger.setLevel(logging.DEBUG)  # Capture all logs DEBUG and above

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

series_descriptions_list = []
series_instance_uids_list = []
study_instance_uids_list = []
patient_names_list = []

def extract_dicom_info(dicom_files):
    for dcm_file in dicom_files:
        try:
            ds = pydicom.dcmread(dcm_file, stop_before_pixels=True)
            patient_name = str(ds.PatientName) if "PatientName" in ds else "Unknown"
            series_description = str(ds.SeriesDescription) if "SeriesDescription" in ds else "N/A"
            series_instance_uid = str(ds.SeriesInstanceUID) if "SeriesInstanceUID" in ds else "N/A"
            study_instance_uid = str(ds.StudyInstanceUID) if "StudyInstanceUID" in ds else "N/A"

            if patient_name not in patient_names_list:
                patient_names_list.append(patient_name)
            if series_description not in series_descriptions_list:
                series_descriptions_list.append(series_description)
            if series_instance_uid not in series_instance_uids_list:
                series_instance_uids_list.append(series_instance_uid)
            if study_instance_uid not in study_instance_uids_list:
                study_instance_uids_list.append(study_instance_uid)
        except Exception as e:
            logger.error(f"⚠️ Error reading {dcm_file}: {e}")



def push_single_association(dataset_path, IP, port):
    logger.info("Starting to push via Single Association \n")
    # Get the list of DICOM files recursively from all subdirectories
    dicom_files = glob.glob(f"{dataset_path}/**/*.dcm", recursive=True)

    if not dicom_files:
        logger.error(f"❌ No DICOM files found in {dataset_path}")
        return

    # Define the storescu command
    # command = ["storescu", IP, port, "-v"] + dicom_files
    command = ["storescu", IP, port, "-v", "+t", "+xi"] + dicom_files

    time.sleep(0.2)  # Short delay before execution

    try:
        subprocess.run(command, check=True)
        logger.info(f"✅ DICOM files successfully sent from: {dataset_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error executing storescu for {dataset_path}: {e}")
        raise RuntimeError(f"storescu command failed for {dataset_path}") from e

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
    failed_datasets = []
    successful_datasets = []

    for dataset_path in datasets:
        try:
            dataset_path = str(dataset_path).strip()
            dicom_files = glob.glob(f"{dataset_path}/**/*.dcm", recursive=True)

            if not dicom_files:
                logger.error(f"⚠️ No DICOM files found in: {dataset_path}")
                failed_datasets.append(dataset_path)
                continue
            extract_dicom_info(dicom_files)
        except Exception as e:
            logger.error(f"❌ Error extracting Dicom Info for dataset at '{dataset_path}': {e}")
            failed_datasets.append(dataset_path)
            continue

    if parallel_push == "True":
        logger.info("parallel data push : True")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=len(datasets)) as executor:
            time.sleep(0.15)
            future_to_dataset = {
                executor.submit(push_single_association, str(dataset).strip(), IP, port): str(dataset).strip()
                for dataset in datasets if str(dataset).strip() not in failed_datasets
            }

            for future in as_completed(future_to_dataset):
                dataset_path = future_to_dataset[future]
                try:
                    future.result()
                    successful_datasets.append(dataset_path)
                    logger.info(f"✅ Successfully completed push for dataset: {dataset_path}")
                except Exception as e:
                    failed_datasets.append(dataset_path)
                    logger.error(f"❌ Failed to push dataset {dataset_path}: {e}")
                    # Continue with other datasets instead of sys.exit()
                    continue

    else:
        logger.info("parallel data push : False")
        time.sleep(0.15)
        for dataset_path in datasets:
            dataset_path_str = str(dataset_path).strip()
            if dataset_path_str in failed_datasets:
                continue

            try:
                if multi_associations == "True":
                    if batch_count >= 2:
                        push_multi_associations(dataset_path_str, IP, port, batch_count, batch_delay)
                    else:
                        logger.warning(f"⚠️ batch_count is {batch_count}, must be >= 2 when using multi_associations. Falling back to single association push.")
                        push_single_association(dataset_path_str, IP, port)
                else:
                    push_single_association(dataset_path_str, IP, port)
                successful_datasets.append(dataset_path_str)
            except Exception as e:
                failed_datasets.append(dataset_path_str)
                logger.error(f"❌ Push failed for dataset {dataset_path_str}: {e}")
                continue  # Continue with next dataset instead of sys.exit()

    # Summary report
    total_datasets = len(datasets)
    logger.info("\n=== Dataset Push Summary ===")
    logger.info(f"Total Datasets: {total_datasets}")
    logger.info(f"Successfully Pushed: {len(successful_datasets)}")
    logger.info(f"Failed: {len(failed_datasets)}")
    if failed_datasets:
        logger.info("Failed Datasets:")
        for failed in failed_datasets:
            logger.info(f"  - {failed}")

    # Only exit with error if all datasets failed
    if len(failed_datasets) == total_datasets:
        logger.error("❌ All dataset pushes failed")
        sys.exit(1)

    return series_descriptions_list, series_instance_uids_list, study_instance_uids_list, patient_names_list


# push_executor("127.0.0.1", "58742", ["/Users/zinnov/Documents/Auto_modules_6_2/test_pulse_data/dataset_bundles/Datasets/Stroke_Demo_Larry_LVO", "/Users/zinnov/Documents/Auto_modules_6_2/test_pulse_data/dataset_bundles/MiniRegression/Hyper"],"True")
