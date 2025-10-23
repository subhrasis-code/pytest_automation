import json
from tabulate import tabulate

# Load JSON
with open("/Users/zinnov/Downloads/data.json") as f:
    data = json.load(f)

# Pick only required fields from each result
rows = []
for item in data["results"]:
    rows.append([
        item.get("workflowType", ""),
        item.get("workflowId", ""),
        item.get("status", ""),
        item.get("executionTime", ""),
        item.get("startTime", ""),
        item.get("endTime", "")
    ])

# Table headers
headers = ["Workflow Type", "Workflow ID", "Status", "Exec Time", "Start Time", "End Time"]

# Print table
print(tabulate(rows, headers=headers, tablefmt="grid"))
