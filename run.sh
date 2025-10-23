#!/bin/bash
# === DEBUG ENVIRONMENT ===

BUILD_PATH_HOME=$1
# This prints the current working directory — the directory where the script is being run from.
echo ":round_pushpin: Running from: $(pwd)"
# Prints the current Linux user running the script.
echo ":test_tube: Whoami: $(whoami)"

# Shows whether Python3, storescu (DCMTK), and kubectl are installed and in the system path.
echo ":snake: Python path: $(which python3 || echo 'Not found')"
echo ":package: DCMTK path (storescu): $(which storescu || echo 'Not found')"
echo ":package: Kubectl path: $(which kubectl || echo 'Not found')"

# This prints current PATH environment variable,
echo ":motorway: PATH=$PATH"

# Show incoming parameters for debug

# Just labels the next part as a Jenkins parameter printout.
echo ":bulb: Jenkins Parameters:"

# Prints environment variables that Jenkins is expected to pass in (dataset location, remote port, push method, etc.).
echo "DATASET_PATH=$DATASET_PATH"
echo "REMOTE_PORT=$REMOTE_PORT"
echo "PUSH_VIA=$PUSH_VIA"
echo "USE_EXTERNAL_IP=$USE_EXTERNAL_IP"
echo "MULTI_ASSOCIATIONS=$MULTI_ASSOCIATIONS"
echo "MULTI_ASSOCIATIONS_BATCH_COUNT=$MULTI_ASSOCIATIONS_BATCH_COUNT"
echo "MULTI_ASSOCIATIONS_BATCH_DELAY=$MULTI_ASSOCIATIONS_BATCH_DELAY"
echo "ASSERT_AFTER_PUSH=$ASSERT_AFTER_PUSH"
echo "KUBECONFIG_FILE=$KUBECONFIG_FILE"
echo "siteName=$siteName"
echo "parallel_push=$parallel_push"
echo "waitPop=$waitPop"
echo "UNIQUE_ID=$BUILD_ID"
echo "Build name: $BUILD_DISPLAY_NAME"
echo "Job name: $JOB_NAME"
echo "Build number: $BUILD_NUMBER"
echo "Build path: $BUILD_PATH_HOME"

# Copies the original global.json to the Jenkins workspace for editing.
global_json_file="/onPrem/pytest_automation/global.json"
cp "$global_json_file" "$BUILD_PATH_HOME/global.json"
# Stores the workspace path to the copied JSON and exports it as an environment variable for Python to use.
global_json_file_workspace="$BUILD_PATH_HOME/global.json"
export GLOBAL_JSON_FILE="$global_json_file_workspace"


# === SETUP ENVIRONMENT ===
# Adds extra directories to the $PATH (like DCMTK tools).
export PATH="/opt/rapid4/dcmtk/bin:/usr/local/bin:$PATH"
# Go to script directory. Changes directory to the location of the script file.
cd "$(dirname "$0")"

# === CONFIGURATION ===
GLOBAL_JSON_FILE="$global_json_file_workspace"
#export GLOBAL_JSON_FILE
echo ":page_facing_up: Using GLOBAL_JSON_FILE=$GLOBAL_JSON_FILE"

# === JSON PATCHING ===
echo ":wrench: Updating $GLOBAL_JSON_FILE with Jenkins environment variables..."
jq  --arg dataset_path "$DATASET_PATH" \
    --arg remote_port "$REMOTE_PORT" \
    --arg push_via "$PUSH_VIA" \
    --arg use_external_ip "$USE_EXTERNAL_IP" \
    --arg multi_associations "$MULTI_ASSOCIATIONS" \
    --arg multi_asso_batch_count "$MULTI_ASSOCIATIONS_BATCH_COUNT" \
    --arg multi_asso_batch_delay "$MULTI_ASSOCIATIONS_BATCH_DELAY" \
    --arg assert_after_push "$ASSERT_AFTER_PUSH" \
    --arg kubeConfigFile "$KUBECONFIG_FILE" \
    --arg siteName "$siteName" \
    --arg parallel_push "$parallel_push" \
    --arg waitPop "$waitPop"\
    '
     .upload_dataset_params.dataset_path = $dataset_path |
     .upload_dataset_params.remote_port = $remote_port |
     .upload_dataset_params.parallel_push = $parallel_push |
     .push_via = $push_via |
     .clear_site = $clear_site |
     .use_external_ip = $use_external_ip |
     .multi_associations = $multi_associations |
     .multi_asso_batch_count = ($multi_asso_batch_count | tonumber) |
     .multi_asso_batch_delay = ($multi_asso_batch_delay | tonumber) |
     .assert_after_push = $assert_after_push |
     .kubeConfigFile = $kubeConfigFile |
     .siteName = $siteName |
     .upload_dataset_params.waitPop = ($waitPop | tonumber)
     ' "$GLOBAL_JSON_FILE" > temp.json && mv temp.json "$GLOBAL_JSON_FILE"
echo ":white_check_mark: global.json updated:"
cat "$GLOBAL_JSON_FILE"

# === RUN TEST ===
echo ":rocket: Running pytest..."
export PYTHONUNBUFFERED=1
pytest -s UploadDatasetParallel/test_upload_dataset.py --html=report.html --self-contained-html