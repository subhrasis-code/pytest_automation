import boto3

def get_s3_module_and_filename(module):
    s3_module_name = ""
    output_file = ""
    try:
        if module == "PETN":
            s3_module_name = "CTPA"
            output_file = "outputjson.json"
        elif module == "RVLV":
            s3_module_name = "RVLV"
            output_file = "outputjson.json"
        elif module == "Mismatch":
            s3_module_name = "Mismatch"
            output_file = "outputjson.json"
        elif module == "ANRTN":
            s3_module_name = "ANRTN"
            output_file = "outputjson.json"
        elif module == "hemorrhage":
            s3_module_name = "hemorrhage"
            output_file = "outputjson.json"
        elif module == "Hyperdensity":
            s3_module_name = "Hyperdensity"
            output_file = "outputjson.json"
        elif module == "Hypodensity":
            s3_module_name = "Hypodensity"
            output_file = "outputjson.json"
        elif module in {"NCCTStroke", "NCCT"}:
            s3_module_name = "LVO_ON_NCCT"
            output_file = "outputjson.json"
        elif module == "Octopus":
            s3_module_name = "ASPECTS"
            output_file = "outputjson.json"
        elif module == "angio":
            s3_module_name = "CTA"
            output_file = "outputjson.json"
        elif module == "neuro3d":
            s3_module_name = "NEURO3D"
            output_file = "output.json"
        elif module == "sdh":
            s3_module_name = "SDH"
            output_file = "output.json"
        else:
            return f"Invalid module name: {module}"

        return s3_module_name, output_file
    except Exception as e:
        return f"Error: {e}"

def get_jm_data(label):
    json_path = label.split(" ")[-1]
    parts = json_path.split("/")
    site = parts[-4]
    module = parts[-3]
    task = parts[-2]
    return module, task, site

def get_s3_list(s3, prefix, s3_bucket_name):
	# list objects : lists all files & folders under a given folder path in bucket.
	# list_objects_v2 : aws api
	response = s3.list_objects_v2(Bucket=s3_bucket_name, Prefix=prefix)
	return response

def read_s3_file(s3, component, s3_bucket_name):
	# Get the object : fetches a single file’s content — so we can read, parse, or process it in Python.
	# get_object : aws api
	json_response = s3.get_object(Bucket=s3_bucket_name, Key=component)

	# Read and print the content : Body → this is the actual file content (stream)
	content = json_response["Body"].read().decode("utf-8")
	return content


def s3_check_executor(s3_module_name, site, s3_json_file, s3_task_prefix, systemCode, s3_bucket_name, aws_profile):
	s3_list = []
	s3_file_content = ""

	# Create a boto3 session using SSO profile : authenticates with the AWS account.
	session = boto3.Session(profile_name=aws_profile)
	# Create an S3 client : prepares Python code to talk to S3.
	s3 = session.client("s3")

	prefix = f"{systemCode}/{site}/{s3_module_name}/{s3_task_prefix}"
	objects = get_s3_list(s3, prefix, s3_bucket_name)

	for key, value in objects.items():
		if key == "Contents":
			content_metadata = value
			for item in content_metadata:
				for key, value in item.items():
					if key == "Key":
						s3_list.append(value)

	for component in s3_list:
		if s3_json_file in component:
			s3_file_content = read_s3_file(s3, component, s3_bucket_name)

	return s3_list, s3_file_content


def s3_runner(label, systemCode, s3_bucket_name, aws_profile):
    module, task, site = get_jm_data(label)
    s3_module_name, s3_json_file = get_s3_module_and_filename(module)
    s3_task_prefix = task.split("_")[0]+"_"
    s3_list, s3_file_content = s3_check_executor(s3_module_name, site, s3_json_file, s3_task_prefix, systemCode, s3_bucket_name, aws_profile)

    return s3_list, s3_file_content
    # print (s3_list, s3_file_content)

label = "[Rapid RV/LV] /rapid_data/task_data/site2/RVLV/15_15/output.json"
systemCode = "vo_system"
s3_bucket_name = "ischemaview-qa2-us-west-2"
aws_profile = "qa2"

s3_list, s3_file_content = s3_runner(label, systemCode, s3_bucket_name, aws_profile)
print(s3_list)
print(s3_file_content)





