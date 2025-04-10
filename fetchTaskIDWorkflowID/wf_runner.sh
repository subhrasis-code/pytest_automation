#!/bin/bash

# Get the arguments passed from the Python script
onPrem_kubeconfig=$1
onPrem_conductor_server=$2
onPrem_local_port=$3
onPrem_remote_port=$4

onCloud_kubeconfig=$5
onCloud_conductor_server=$6
onCloud_local_port=$7
onCloud_remote_port=$8

wftrackerpy_file_path=$9
duration=${10}
c_ids_file_path=${11}
performance_report_path=${12}

namespace=${13}

# ---------------------------------------- For On-prem & On-cloud----------------------------------------

# Set up kubeconfigs and port forwarding commands
export KUBECONFIG=$onPrem_kubeconfig
kubectl port-forward $onPrem_conductor_server -n $namespace $onPrem_local_port:$onPrem_remote_port &

export KUBECONFIG=$onCloud_kubeconfig
kubectl port-forward $onCloud_conductor_server -n $namespace $onCloud_local_port:$onCloud_remote_port &

# Sleep for a short period to ensure port forwarding is established
sleep 5

# Run the Python script with the necessary environment variables
CONDUCTOR_SERVER="http://localhost:$onPrem_local_port/api" CLOUD_CONDUCTOR_SERVER="http://localhost:$onCloud_local_port/api" python3 $wftrackerpy_file_path --duration=$duration -cf $c_ids_file_path -d -s -f $performance_report_path






# ---------------------------------------- Only for On-prem ----------------------------------------

# Set up kubeconfigs and port forwarding commands
#export KUBECONFIG=$onPrem_kubeconfig
#kubectl port-forward $onPrem_conductor_server -n $namespace $onPrem_local_port:$onPrem_remote_port &
#
#
#CONDUCTOR_SERVER="http://localhost:$onPrem_local_port/api"  python3 $wftrackerpy_file_path --duration=$duration -cf $c_ids_file_path -d -s -f $performance_report_path
