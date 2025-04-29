#!/bin/bash
# === DEBUG ENVIRONMENT ===
echo ":round_pushpin: Running from: $(pwd)"
echo ":test_tube: Whoami: $(whoami)"

# === ACTIVATE VENV ===
echo ":sparkles: Activating virtual environment..."
source /Users/zinnov/Documents/Auto_modules_6_2/onPrem/pytest_automation/.venv/bin/activate

echo ":snake: Python path: $(which python3 || echo 'Not found')"
echo ":package: DCMTK path (storescu): $(which storescu || echo 'Not found')"
echo ":package: Kubectl path: $(which kubectl || echo 'Not found')"
echo ":motorway: PATH=$PATH"

# Show incoming parameters for debug
echo ":bulb: Jenkins Parameters:"
echo "DATASET_PATH1=$DATASET_PATH1"
echo "REMOTE_PORT=$REMOTE_PORT"
echo "PUSH_VIA=$PUSH_VIA"
echo "KUBECONFIG_FILE=$KUBECONFIG_FILE"
echo "siteName=$siteName"
echo "parallel_push=$parallel_push"
echo "waitPop=$waitPop"

# === SETUP ENVIRONMENT ===
export PATH="/opt/rapid4/dcmtk/bin:/usr/local/bin:$PATH"
# Go to script directory
cd "$(dirname "$0")"
# === CONFIGURATION ===
GLOBAL_JSON_FILE="global.json"
export GLOBAL_JSON_FILE
echo ":page_facing_up: Using GLOBAL_JSON_FILE=$GLOBAL_JSON_FILE"
# === JSON PATCHING ===
if [[ -n "$DATASET_PATH1" && -n "$REMOTE_PORT" && -n "$PUSH_VIA" && -n "$KUBECONFIG_FILE" && -n "$siteName" ]]; then
  echo ":wrench: Updating $GLOBAL_JSON_FILE with Jenkins environment variables..."
  jq --arg dataset_path1 "$DATASET_PATH1" \
     --arg remote_port "$REMOTE_PORT" \
     --arg push_via "$PUSH_VIA" \
     --arg kubeConfigFile "$KUBECONFIG_FILE" \
     --arg siteName "$siteName" \
     --arg parallel_push "$parallel_push" \
	 --arg waitPop "waitPop"\
     '
     .upload_dataset_params.dataset_path1 = $dataset_path1 |
     .upload_dataset_params.remote_port = $remote_port |
     .upload_dataset_params.parallel_push = $parallel_push |
     .push_via = $push_via |
     .kubeConfigFile = $kubeConfigFile |
     .siteName = $siteName
     ' "$GLOBAL_JSON_FILE" > temp.json && mv temp.json "$GLOBAL_JSON_FILE"
  echo ":white_check_mark: global.json updated:"
  cat "$GLOBAL_JSON_FILE"
else
  echo ":information_source: Jenkins environment variables not fully provided. Skipping JSON patch."
fi
# === RUN TEST ===
echo ":rocket: Running pytest..."
/Users/zinnov/Documents/Test_data_generator/.venv/bin/pytest -s UploadDatasetParallel/test_upload_dataset.py --html=report.html --self-contained-html