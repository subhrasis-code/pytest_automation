import subprocess
import tempfile
import os

# ================= USER CONFIG =================
modules_to_enable = ["SDH", "ASPECTS"]
cloudprocessing = True
pacs_dispatch = True
# ===============================================

POD_NAME = "rapid-jobmanager-7d5fb96d86-lsgrc"
NAMESPACE = "rapid-apps"
XML_PATH = "/opt/rapid4/site1/isv_service_config.xml"
TMP_SCRIPT = "/tmp/update_legacy_modules.py"

LEGACY_MAP = {
    "SDH": "enablesdh",
    "ASPECTS": "enableaspects",
    "CTA": "enablecta",
    "ICH": "enableich",
    "MISMATCH": "enablemismatch",
    "NEURO3D": "enableneuro3d",
    "ANRTN": "enableanrtn",
    "IPE": "enableipe",
    "NCCTSTROKE": "enablencctstroke",
    "PETN": "enablepetn",
    "RVLV": "enablervlv",
    "HYPODENSITY": "hypodensitystandalone",
    "HYPERDENSITY": "enablehyperdensity",
    "SP": "enablesurgicalpreview"
}

python_script = f"""
import xml.etree.ElementTree as ET

tree = ET.parse("{XML_PATH}")
root = tree.getroot()
jm = root.find("jobmanager")

modules_to_enable = {modules_to_enable}
cloudprocessing = "{str(cloudprocessing).lower()}"
pacs_dispatch = "{str(pacs_dispatch).lower()}"
legacy_map = {LEGACY_MAP}

# Update legacy flags
for module, xml_key in legacy_map.items():
    el = jm.find(xml_key)
    if el is not None:
        el.text = "1" if module in modules_to_enable else "0"

# Update modules section
modules_section = jm.find("modules")
for mod in modules_section.findall("module"):
    name = mod.findtext("modulename")
    if name in modules_to_enable:
        cp = mod.find("cloudprocessing")
        if cp is not None:
            cp.text = cloudprocessing
        epd = mod.find("enable_pacs_dispatch")
        if epd is not None:
            epd.text = pacs_dispatch

tree.write("{XML_PATH}")
print("XML update completed successfully")
"""

# 1. Copy temp script into pod
subprocess.run(
    ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--",
     "sh", "-c", f"cat > {TMP_SCRIPT} << 'EOF'\n{python_script}\nEOF"],
    check=True
)

# 2. Execute script inside pod
subprocess.run(
    ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--", "python3", TMP_SCRIPT],
    check=True
)

# 3. Cleanup
subprocess.run(
    ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--", "rm", "-f", TMP_SCRIPT],
    check=True
)
