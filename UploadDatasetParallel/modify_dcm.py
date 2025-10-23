import argparse
import json
import os
import sys

import pydicom
import random
import string

from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from faker import Faker
from loguru import logger
from random import randint, choice

from pydicom.uid import generate_uid

def modify_input_data(patient_info_file_path, datasets_path, patient_issuer_id, st_date, st_time):
    logger.info("Modifying the input data with new values")

    if len(patient_info_file_path) == 0:
        patient_info = generate_patient_data()
    else:
        patient_info = json.loads(read_file(os.path.expanduser(patient_info_file_path)))

    patient_info['patientIssuerID'] = patient_issuer_id
    directories = [d for d in os.listdir(datasets_path) if os.path.isdir(os.path.join(datasets_path, d))
                   and not d.startswith('.')]

    modified_data = {}
    modified_files_list = []

    print(f"---Patient Demographics--- \n"
          f"\tPatient Name: {patient_info['patientName']}\n"
          f"\tPatient Birth Date: {patient_info['patientBirthDate']}\n"
          f"\tPatient ID: {patient_info['patientID']}\n"
          f"\tPatient Sex: {patient_info['patientSex']}\n"
          f"\tPatients Age: {patient_info['patientsAge']}\n"
          f"\tPatient IssuerID: {patient_info['patientIssuerID']}\n\n"


          f"\t\"patientName\": \"{patient_info['patientName']}\",\n"
          f"\t\"patientBirthDate\": \"{patient_info['patientBirthDate']}\",\n"
          f"\t\"patientID\": \"{patient_info['patientID']}\",\n"
          f"\t\"patientSex\": \"{patient_info['patientSex']}\",\n"
          f"\t\"patientsAge\": \"{patient_info['patientsAge']}\",\n"
          f"\t\"Patient IssuerID\": \"{patient_info['patientIssuerID']}\"\n\n"
          f"---UID DETAILS and Study Details:---")
    for directory in directories:
        full_directory_path = os.path.join(datasets_path, directory)
        # Walk through the directory
        modified_data['patient_info'] = {}
        patient_info['study_date'] = format_date_as_yyyymmdd(get_study_date())
        patient_info['series_date'] = patient_info['study_date']
        study_time = get_study_time()
        patient_info['study_time'] = study_time
        patient_info['series_time'] = study_time

        patient_info['acquisition_date'] = patient_info['study_date']
        patient_info['acquisition_time'] = patient_info['study_time']
        patient_info['timezone_offset_from_utc'] = random.choice(
            ["-0100", "-0230", "-0400", "+0100", "+0230", "+0330", "+0400", "+0530"])
        patient_info['kvp'] = random.choice([100, 110, 120, 130, 140])
        patient_info['gantryTilt'] = random.choice([0, 1, 2, 3, 4, 10, 11, 12, 13])

        series_file_map = get_dicom_file_list(str(full_directory_path))
        patient_info['accessionNumber'] = generate_id(10)

        if st_date == 0:
            patient_dob = datetime.strptime(patient_info['patientBirthDate'], '%Y%m%d').date()
            new_study_date = Faker().date_time_between(patient_dob, datetime.now())
            patient_info['studyDate'] = format_date_as_yyyymmdd(new_study_date)
            patient_info['seriesDate'] = patient_info['studyDate']
            patient_info['patientsAge'] = get_age(patient_dob, new_study_date)
        if st_time == 0:
            study_time = get_study_time()
            patient_info['studyTime'] = study_time
            patient_info['seriesTime'] = study_time
        study_instance_uid = generate_uid()

        modified_data['patient_info'].update(patient_info)
        modified_data['study_uid'] = study_instance_uid
        modified_data['series_uid'] = {}

        total_images_modified = 0
        number_of_frames = None

        print(f"Directory Path: {full_directory_path}\n"
              f"Study Instance Uid: {modified_data['study_uid']}"
              f" | Accession Number: {modified_data['patient_info']['accessionNumber']}"
              f" | Study Date: {modified_data['patient_info']['studyDate']}"
              f" | Study Time: {modified_data['patient_info']['studyTime']}\n"
              f"---Series Details---")
        patient_info['number_of_study_related_series'] = len(series_file_map)
        study_related_instances = 0
        modalities_in_study = ""
        for key in series_file_map:
            if isinstance(series_file_map[key], list):
                study_related_instances += len(series_file_map[key])
            se_modality = get_dicom_tag_value(series_file_map[key][0], (0x0008, 0x0060))
            if se_modality not in modalities_in_study:
                modalities_in_study = modalities_in_study + se_modality
        patient_info['number_of_study_related_instances'] = study_related_instances

        for series in series_file_map:
            series_instance_uid = generate_uid()

            # logger.info(f"Generated new SeriesInstanceUID: {series_instance_uid}")
            series_image_count = 0
            series_description = ""
            series_modality = ""
            patient_info['number_of_series_related_instances'] = len(series_file_map[series])
            patient_info['modalities_in_study'] = modalities_in_study
            for file in series_file_map[series]:
                patient_info['number_of_series_related_instances'] = len(series_file_map[series])

                modified_ds = modify_dicom_file(file, patient_info, study_instance_uid, series_instance_uid)
                # copyfile(file, file.replace("dcm", "dcm.bak"))
                series_image_count += 1

                modified_ds.save_as(str(file))
                modified_files_list.append(file)
                if 'NumberOfFrames' in modified_ds and number_of_frames is None:
                    number_of_frames = get_dicom_tag_value(file, (0x0028, 0x0008))
                series_description = get_dicom_tag_value(file, (0x0008, 0x103e))
                series_modality = get_dicom_tag_value(file, (0x0008, 0x0060))

            print(f"\tSeries Instance Uid: {series_instance_uid} | Image Count: {series_image_count} "
                  f"| Series Modality: {series_modality} | Series Description: {series_description}")

            total_images_modified += series_image_count
            modified_data['series_uid'][series_instance_uid] = series_image_count if number_of_frames is None \
                else number_of_frames
            # logger.info(f"Updated {series_image_count} dcm files in series {series_instance_uid}")
        # logger.info(f"Total {total_images_modified} dcm files updated in study {study_instance_uid}")
        print("\n")
    return modified_data, modified_files_list


def modify_dicom_file(dicom_file, patient_info, study_instance_uid, series_instance_uid):
    # print(f"{dicom_file}")
    ds = pydicom.dcmread(dicom_file)
    # Apply patient modifications
    if 'patientName' in patient_info:
        add_or_modify_tag(ds, (0x0010, 0x0010), 'PN', patient_info['patientName'])
    if 'patientSex' in patient_info:
        add_or_modify_tag(ds, (0x0010, 0x0040), 'CS', patient_info['patientSex'])
    if 'patientBirthDate' in patient_info:
        add_or_modify_tag(ds, (0x0010, 0x0030), 'DA', patient_info['patientBirthDate'].replace('-', ''))

    # Apply study modifications
    if 'patientID' in patient_info:
        add_or_modify_tag(ds, (0x0010, 0x0020), 'LO', patient_info['patientID'])
    if 'accessionNumber' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0050), 'SH', patient_info['accessionNumber'])
    if 'patientIssuerID' in patient_info:
        add_or_modify_tag(ds, (0x0010, 0x0021), 'LO', patient_info['patientIssuerID'])
        add_or_modify_tag(ds, (0x0008, 0x0080), 'LO', patient_info['patientIssuerID'])
    if 'acquisition_date' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0022), 'DA', patient_info['acquisition_date'].replace('-', ''))
    if 'studyDate' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0020), 'DA', patient_info['study_date'].replace('-', ''))
    if 'seriesDate' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0021), 'DA', patient_info['series_date'].replace('-', ''))
    if 'acquisition_time' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0032), 'TM', patient_info['acquisition_time'].replace('-', ''))
    if 'studyTime' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0030), 'TM', patient_info['study_time'].replace('-', ''))
    if 'seriesTime' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0031), 'TM', patient_info['series_time'].replace('-', ''))
    if 'timezone_offset_from_utc' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0201), 'SH', patient_info['timezone_offset_from_utc'].replace('-', ''))
    if 'patientsAge' in patient_info:
        add_or_modify_tag(ds, (0x0010, 0x1010), 'AS', patient_info['patientsAge'])
    if 'kvp' in patient_info:
        add_or_modify_tag(ds, (0x0018, 0x0060), 'DS', patient_info['kvp'])

    if 'number_of_study_related_series' in patient_info:
        add_or_modify_tag(ds, (0x0020, 0x1206), 'IS', patient_info['number_of_study_related_series'])
    if 'number_of_study_related_instances' in patient_info:
        add_or_modify_tag(ds, (0x0020, 0x1208), 'IS', patient_info['number_of_study_related_instances'])
    if 'number_of_series_related_instances' in patient_info:
        add_or_modify_tag(ds, (0x0020, 0x1209), 'IS', patient_info['number_of_series_related_instances'])
    # if 'slice_thickness' in patient_info:
    add_or_modify_tag(ds, (0x0018, 0x0050), 'DS', 1.0000)
    if 'modalities_in_study' in patient_info:
        add_or_modify_tag(ds, (0x0008, 0x0061), 'CS', patient_info['modalities_in_study'])

    faker = Faker()
    add_or_modify_tag(ds, (0x0008, 0x1050), 'PN', random.choice([faker.name_male(), faker.name_female()]))
    add_or_modify_tag(ds, (0x0008, 0x1048), 'PN', random.choice([faker.name_male(), faker.name_female()]))
    add_or_modify_tag(ds, (0x0008, 0x1070), 'PN', random.choice([faker.name_male(), faker.name_female()]))
    add_or_modify_tag(ds, (0x0008, 0x0090), 'PN', random.choice([faker.name_male(), faker.name_female()]))
    add_or_modify_tag(ds, (0x0008, 0x009C), 'PN', random.choice([faker.name_male(), faker.name_female()]))
    add_or_modify_tag(ds, (0x0008, 0x1060), 'PN', random.choice([faker.name_male(), faker.name_female()]))
    add_or_modify_tag(ds, (0x0008, 0x1040), 'LO', "Scan Department")
    add_or_modify_tag(ds, (0x0040, 0x0243), 'SH', "Building Name")
    add_or_modify_tag(ds, (0x0040, 0x1002), 'LO', "for diagnostic purpose")
    add_or_modify_tag(ds, (0x0020, 0x0060), 'CS', random.choice(['R', 'L']))
    add_or_modify_tag(ds, (0x0040, 0x0551), 'LO', "sample specimen identifier")

    if ds.Modality == 'MR' and 'gantryTilt' in patient_info:
        add_or_modify_tag(ds, (0x0018, 0x1120), 'DS', patient_info['gantryTilt'])

    ds.StudyInstanceUID = study_instance_uid
    ds.SeriesInstanceUID = series_instance_uid
    ds.SOPInstanceUID = generate_uid()

    return ds


def get_dicom_file_list(dataset_path):
    # Get the list of DICOM files in the directory
    series_file_map = {}
    for root, _, files in os.walk(dataset_path):
        dicom_files = []

        for file in files:
            # Create the full file path and add it to the list
            if file.endswith('.dcm'):
                if file not in dicom_files:
                    full_path = os.path.join(root, file)
                    dicom_files.append(full_path)
        if len(dicom_files) != 0:
            series_file_map[root] = dicom_files

            assert len(
                series_file_map) != 0, f"\n!-----------------No files identified for modification-----------------!\n"

    return series_file_map


def add_or_modify_tag(ds, tag, vr, value):
    """Add a DICOM tag if it does not exist, or modify it if it does."""
    if tag in ds:
        # print(f"{ds[tag].value} - {tag} - {vr} - {value}")
        ds[tag].value = value
    else:
        ds.add_new(tag, vr, value)
        # print(f"{ds[tag].value} - {tag} - {vr} - {value}")


def get_dicom_tag_value(dicom_file, tag):
    ds = pydicom.dcmread(dicom_file)
    if tag in ds:
        return ds[tag].value
    else:
        return None


def get_study_date():
    return Faker().date_this_month(before_today=True)


def get_study_time():
    return format_time_as_hhmmss(Faker().date_time_this_month(before_now=True))


def generate_patient_data():
    faker = Faker()

    # Randomly choose gender
    gender_list = ['M', 'F']
    gender = random.choice(gender_list)
    name = generate_name(faker, gender)
    # Generate random birthdate between 1924 and 2023
    patient_dob = faker.date_time_between_dates(datetime_start=datetime(1925, 1, 1, 00, 00, 00))

    # Generate random study date, ensuring it is after the birthdate
    study_date = get_study_date()

    # Generate random study Time, ensuring it is after the birthdate
    study_time = get_study_time()

    # Get age at time of the study
    patient_age = get_age(patient_dob, study_date)

    patient_data = {
        "patientName": name,
        "patientBirthDate": format_date_as_yyyymmdd(patient_dob),
        "patientSex": gender,
        "patientID": generate_id(10),
        "studyDate": format_date_as_yyyymmdd(study_date),
        "seriesDate": format_date_as_yyyymmdd(study_date),
        "studyTime": study_time,
        "seriesTime": study_time,
        "patientsAge": patient_age
    }
    return patient_data


def generate_name(faker, gender):
    # Generate a name based on the gender
    if gender == 'male':
        return faker.first_name_male() + "^" + faker.first_name() + "^" + faker.last_name()
    else:
        return faker.first_name_female() + "^" + faker.first_name() + "^" + faker.last_name()


def generate_id(length=10):
    # Define the possible characters (uppercase, lowercase, digits)
    characters = string.ascii_uppercase + string.digits

    # Randomly select 'length' characters from the pool
    return ''.join(choice(characters) for _ in range(length))


def get_random_date(start="-30y", end="today"):
    faker = Faker()
    random_date = faker.date_between(start_date=str(start), end_date=end)
    return format_date_as_yyyymmdd(random_date)


def get_random_time():
    faker = Faker()
    random_date = faker.date_time_this_month(before_now=True)
    return format_time_as_hhmmss(random_date)


def format_date_as_yyyymmdd(date):
    # Format dates as 'yyyymmdd'
    return date.strftime('%Y%m%d')


def format_time_as_hhmmss(date):
    # Format the time as 'HHmmssSSS'
    return date.strftime('%H:%M:%S').replace(":", "")


def get_age(birth_date, study_date):
    age = relativedelta(study_date, birth_date).years
    if age < 10:
        return f'00{age}Y'
    elif 10 <= age <= 99:
        return f'0{age}Y'
    else:
        return f'{age}Y'


def read_file(local_file_path):
    # Open the file in read mode
    with open(local_file_path, 'r') as file:
        # Read the entire content of the file
        content = file.read()

    return content


def get_inputs(*, patient_info_file_path: str, datasets_path: str, patient_issuer_id: str, study_date: int,
               study_time: int) -> None:
    # print(f"args datasets path length : {len(args.datasets_path)}")
    # print(f"args datasets exists : {os.path.exists(datasets_path)}")
    # print(f"args.datasets_path: {args.datasets_path}")
    # print(f"datasets_path: {datasets_path}")

    if len(args.datasets_path) == 0 or not os.path.exists(datasets_path):
        # print(f"args.datasets_path: {args.datasets_path}")
        # print(f"datasets_path: {datasets_path}")
        logger.error("Provide a valid path for directory with parameter --path")
        sys.exit(1)
    if args.patient_issuer_id is None:
        logger.error("Missing argument for patient_issuer_id")
        sys.exit(1)
    elif len(args.patient_issuer_id) == 0:
        logger.info("Value for patient Issuer is set as an empty string. No patient ID will be added to the data.")

    modify_input_data(patient_info_file_path, datasets_path, patient_issuer_id, study_date, study_time)


if __name__ == "__main__":
    start_time = datetime.now()
    try:
        parser = argparse.ArgumentParser(description='Arguments for modifyDcm.py')
        parser.add_argument('--patient_info', action="store", dest='patient_info_file_path')
        parser.add_argument('--path', action="store", dest='datasets_path')
        parser.add_argument('--issuer', dest='patient_issuer_id', default="")
        parser.add_argument('--studyDate', action="store", dest='study_date')
        parser.add_argument('--studyTime', action="store", dest='study_time')

        args = parser.parse_args()
        if args.patient_info_file_path is None:
            args.patient_info_file_path = ""
        if args.study_date is None or int(args.study_date) == 0:
            args.study_date = 0

        if args.study_time is None or int(args.study_time) == 0:
            args.study_time = 0

        logger.info(f"datasets_path: {args.datasets_path}")
        logger.info(f"patient_issuer_id: {args.patient_issuer_id}")
        if len(args.datasets_path) == 0:
            logger.error("Missing argument for datasets_path")
            sys.exit(1)
        if args.patient_issuer_id is None:
            logger.error("Missing argument for patient_issuer_id")
            sys.exit(1)
        elif args.patient_issuer_id == "null":
            args.patient_issuer_id = ""
            logger.info("Value for patient Issuer is set as an empty string. No patient ID will be added to the data.")

        if int(args.study_date) == 1:
            args.study_date = 1
            logger.info(f"studies will be generated with same date.")
        else:
            logger.info(f"Studies will be generated with different dates.")
        if int(args.study_time) == 1:
            args.study_time = 1
            logger.info(f"Studies will be generated with same timestamps.")
        else:
            logger.info(f"Studies will be generated with different timestamps.")
        get_inputs(datasets_path=os.path.expanduser(args.datasets_path),
                   patient_info_file_path=args.patient_info_file_path, patient_issuer_id=args.patient_issuer_id,
                   study_date=args.study_date, study_time=args.study_time)

    except ValueError:
        logger.error("Required parameter missing in the arguments.")

    end_time = datetime.now()
    time_taken_to_modify_data = end_time - start_time
    print(f"Time taken to modify data: {time_taken_to_modify_data}")
