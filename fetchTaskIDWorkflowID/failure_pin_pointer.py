import json

import requests
from cloudConductor_functions import find_key


# conductorUI_local_port = "5000"
# workflow_id = "e0df1ddb-096e-485c-9633-78106eb3b926"

def pinpointError(conductorUI_local_port, workflow_id):
    print("\nInside pinpointError method.")
    pinpoint_log = ""
    conductor_subworkflow_url = f"http://localhost:{conductorUI_local_port}/api/workflow/{workflow_id}"
    response = requests.get(url=conductor_subworkflow_url, verify=False)
    if response.status_code == 200:
        print(f"PinpointError method : {conductor_subworkflow_url} has status code as 200")
        dict = response.json()
        for innerTasks in range(len(dict["tasks"])):
            taskType = dict["tasks"][innerTasks]["taskType"]
            status = dict["tasks"][innerTasks]['status']
            if status != "COMPLETED" and status != "CANCELED":
                print(f"List number is: {innerTasks}")
                # pinpoint_log += str(str(taskType) + str(dict["tasks"][innerTasks]["reasonForIncompletion"]))
                # print(f"\ntaskType : {taskType}, Status : {status}")
                # print(f"reasonForIncompletion : {dict['tasks'][innerTasks]['reasonForIncompletion']}")
                print(f"taskType : {taskType}, Status : {status}")
                pinpoint_log += f"taskType : {taskType}, Status : {status}"
                x = json.dumps(dict['tasks'][innerTasks])
                y = json.loads(x)
                value = find_key(y, "reasonForIncompletion")
                if value is not False:
                    print(f"\nreasonForIncompletion : {str(dict['tasks'][innerTasks]['reasonForIncompletion'])}")
                    pinpoint_log += f"\nreasonForIncompletion : {dict['tasks'][innerTasks]['reasonForIncompletion']}\n\n"
                else:
                    print("There is no reasonForIncompletion key in the response.")
                    pinpoint_log += "\nThere is no reasonForIncompletion key in the response."
                # print(str(taskType))
                # print(str(dict["tasks"][innerTasks]["reasonForIncompletion"]))
            elif status == "CANCELED":
                print(f"\ntaskType : {taskType}, Status : {status}")
                pinpoint_log += f"taskType : {taskType}, Status : {status}\n"

        # print("********* pinpoint_log *********")
        # print(f"\n\n{pinpoint_log}\n\n")
        return pinpoint_log
    else:
        print(f"ERROR : {conductor_subworkflow_url} has status code as {response.status_code}")

# x = pinpointError(conductorUI_local_port, workflow_id)
# print(x)