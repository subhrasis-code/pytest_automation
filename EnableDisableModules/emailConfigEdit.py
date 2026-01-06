import subprocess
import textwrap

# ---------------- CONFIG ----------------
POD_NAME = "rapid-jobmanager-7d5fb96d86-lsgrc"
NAMESPACE = "rapid-apps"   # change if needed
XML_PATH = "/opt/rapid4/site1/isv_service_config.xml"

NEW_EMAILS = [
    "rapid.receive@ischemaview.com",
    "xyz.@ischemaview.com"
]

SMTP_CONFIG = {
    "smtpserverip": "email-smtp.us-west-2.amazonaws.com",
    "smtpusername": "AKIAXLKMVTTUU2BSCNYI",
    "smtppassword": "BCC1d+JWi2LUXz3Gk0bfME/vTmExsOIm2oekADboSTiO",
    "smtpport": "587",
    "smtpuseextendedparams": "1",
    "serverip": "127.0.0.1",
    "serverport": "1234"
}
# ----------------------------------------


python_inside_pod = f"""
import xml.etree.ElementTree as ET

file_path = "{XML_PATH}"

tree = ET.parse(file_path)
root = tree.getroot()

def set_text(tag, value):
    elem = root.find(".//" + tag)
    if elem is not None:
        elem.text = value

# Update SMTP fields
smtp_config = {SMTP_CONFIG}
for k, v in smtp_config.items():
    set_text(k, v)

# Update rapidreceiveemailaddress
email_elem = root.find(".//rapidreceiveemailaddress")
existing_emails = set()

if email_elem is not None and email_elem.text:
    existing_emails = set(e.strip() for e in email_elem.text.split(","))

new_emails = set({NEW_EMAILS})
final_emails = sorted(existing_emails.union(new_emails))

email_elem.text = ",".join(final_emails)

tree.write(file_path)
print("XML updated successfully")
"""

cmd = [
    "kubectl", "exec", POD_NAME,
    "-n", NAMESPACE,
    "--", "python3", "-c", textwrap.dedent(python_inside_pod)
]

subprocess.run(cmd, check=True)
