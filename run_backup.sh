#!/bin/bash
# === DEBUG ENVIRONMENT ===
echo ":round_pushpin: Running from: $(pwd)"
echo ":test_tube: Whoami: $(whoami)"

# === ACTIVATE VENV ===
echo ":sparkles: Activating virtual environment..."
source /Users/zinnov/Documents/Auto_modules_6_2/onPrem/pytest_automation/.venv/bin/activate

# === INSTALL REQUIREMENTS ===

echo ":snake: Python path: $(which python3 || echo 'Not found')"
echo ":package: DCMTK path (storescu): $(which storescu || echo 'Not found')"
echo ":package: Kubectl path: $(which kubectl || echo 'Not found')"
echo ":motorway: PATH=$PATH"

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

# === SETUP ENVIRONMENT ===
# Adds extra directories to the $PATH (like DCMTK tools).
export PATH="/opt/rapid4/dcmtk/bin:/usr/local/bin:$PATH"
# Go to script directory. Changes directory to the location of the script file.
cd "$(dirname "$0")"

# === CONFIGURATION ===
GLOBAL_JSON_FILE="global.json"
export GLOBAL_JSON_FILE
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
/Users/zinnov/Documents/Test_data_generator/.venv/bin/pytest -s UploadDatasetParallel/test_upload_dataset.py --html=report.html --self-contained-html