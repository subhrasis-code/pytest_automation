shopt -s expand_aliases

source /Users/zinnov/Documents/Auto_modules_6_2/onPrem/pytest_automation/.venv/bin/activate


if [ $# -eq 0 ] || [ $# -eq 1 ]
then
    echo "Please enter two input values."
    echo "	FIRST INPUT is 'path to dcm' files"
    echo "	SECOND INPUT for the 'patient issuer id'. Below is the command format"
    echo "Optional Inputs:"
    echo "	Third INPUT for the file the contains existing patient information."
    echo "	Fourth Input for 'study date'. If all the studies for patient are expected to of same date enter '1' else enter '0'. If not input is provided DFAULT VALUE is '0'"
    echo "	Fifth Input for 'study time'. If all the studies for patient are expected to of same timestamp enter '1' else enter '0'. If not input is provided DFAULT VALUE is '0'"
    echo "Below is the command format"
    echo "	modify_dcm <PATH_TO_FOLDER_CONTAINING_SERIES_OR_LIST_OF_DCM_FILES> <PATIENT_ISSUER_ID> <PATH_TO_PATIENT_INFORMATION_FILE> <STUDY_DATE> <STUDY_TIME>"
    echo "	eg: modify_dcm ~/data/folder_with_studies/study_to_modify GIVE_PATIENT_ISSUER_ID_HERE ~/Desktop/patient_info.json 0 0"
    echo "	eg: modify_dcm ~/data/folder_with_studies/study_to_modify GIVE_PATIENT_ISSUER_ID_HERE ~/Desktop/patient_info.json 0 1"
    echo "	eg: modify_dcm ~/data/folder_with_studies/study_to_modify GIVE_PATIENT_ISSUER_ID_HERE ~/Desktop/patient_info.json 1 0"
    echo "	eg: modify_dcm ~/data/folder_with_studies/study_to_modify GIVE_PATIENT_ISSUER_ID_HERE ~/Desktop/patient_info.json 1 1"
elif [[ $# -eq 2 ]]
then
	study_date='0'
	study_time='0'
	if [[ $2 == "" ]]
	then
		issuer_id=""
	else
		issuer_id=$2
	fi
	echo "Path to dcm: $1"
	echo "Patient Issuer id: $issuer_id"
	echo "No value provided for studyDate and studyTime, each study in the given folder will have unique date and time"
	echo "Executing command python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --patient_info \"\" --studyDate $study_date --studyTime $study_time"
	python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --studyDate $study_date --studyTime $study_time
elif [[ $# -eq 3 ]]
then
	study_date='0'
	study_time='0'
	if [[ $2 == "" ]]
	then
		issuer_id="null"
	else
		issuer_id=$2
	fi
	echo "Path to dcm: $1"
	echo "Patient Issuer id: $issuer_id"
	echo "Patient Demographics file Path: $3"
	echo "No value provided for studyDate and studyTime, each study in the given folder will have unique date and time"
	echo "Executing command python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --patient_info $3 --studyDate $study_date --studyTime $study_time"
	python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --patient_info $3 --studyDate $study_date --studyTime $study_time
elif [[ $# -eq 4 ]]
then
	study_time='0'
	if [[ $2 == "" ]]
	then
		issuer_id=""
	else
		issuer_id=$2
	fi
	echo "Path to dcm: $1"
	echo "Patient Issuer id: $issuer_id"
	echo "Patient Demographics file Path: $3"
	echo "Study Date: $4"
	echo "Executing command python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --patient_info $3 --studyDate $4 --studyTime $$study_time"
	python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --patient_info $3 --studyDate $4 --studyTime $study_time
else
	if [[ $2 == "" ]]
	then
		issuer_id=""
	else
		issuer_id=$2
	fi
	echo "Path to dcm: $1"
	echo "Patient Issuer id: $issuer_id"
	echo "Patient Demographics file Path: $3"
	echo "Study Date: $4"
	echo "Study Time: $5"
	echo "Executing command python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --patient_info $3 --studyDate $4 --studyTime $5"
	python3 ~/Documents/Auto_modules_6_2/onPrem/pytest_automation/UploadDatasetParallel/modify_dcm.py --path $1 --issuer $issuer_id --patient_info $3 --studyDate $4 --studyTime $5
fi