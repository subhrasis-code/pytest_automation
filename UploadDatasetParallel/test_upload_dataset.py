# This function is invoked when running with pytest
import sys
import os
import json
import pytest

# ✅ Add the current script directory to the module search path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from upload_dataset_main import executor, dataset_list
from retrievePatienID import get_patient_id

@pytest.mark.skipif("GLOBAL_JSON_FILE" not in os.environ, reason="Missing GLOBAL_JSON_FILE env var")
def test_run_upload_dataset():
    global_json_path = os.environ["GLOBAL_JSON_FILE"]

    with open(global_json_path, 'r') as f:
        global_data = json.load(f)

    datasets = dataset_list(global_data["upload_dataset_params"])
    get_patient_id(datasets)

    executor(global_data["kubeConfigFile"], global_data["upload_dataset_params"]['remote_port'],
             global_data['namespace'],
             global_data["upload_dataset_params"]['IP'], datasets,
             global_data["upload_dataset_params"]["parallel_push"],
             global_data["kubeConfigFile"], global_data["tomcatServer_local_port"],
             global_data["tomcatServer_remote_port"],
             global_data["tomcatServer_username"], global_data["tomcatServer_password"], global_data["siteName"],
             global_data["upload_dataset_params"]['waitPop'],
             global_data["upload_dataset_params"]['statusCheckInterval'],
             global_data["push_via"])