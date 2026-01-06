import subprocess
import textwrap

# ---------------- USER INPUT ----------------
POD_NAME = "rapid-jobmanager-7d5fb96d86-lsgrc"
NAMESPACE = "rapid-apps"
XML_PATH = "/opt/rapid4/site1/isv_service_config.xml"

MODULES_TO_UPDATE = ["OH", "MLS", "VO", "CSPINE"]
ENABLE_VALUE = "true"   # "true" or "false"
# -------------------------------------------

TMP_SCRIPT = "/tmp/update_new_modules.py"

python_code = textwrap.dedent(f"""
    import xml.etree.ElementTree as ET

    tree = ET.parse("{XML_PATH}")
    root = tree.getroot()
    jm = root.find("jobmanager")

    modules_to_update = {MODULES_TO_UPDATE}
    enable_value = "{ENABLE_VALUE}"

    modules_section = jm.find("modules")

    updated = []

    for mod in modules_section.findall("module"):
        name = mod.findtext("modulename")
        if name in modules_to_update:
            enable_tag = mod.find("enable")
            if enable_tag is not None:
                enable_tag.text = enable_value
                updated.append(name)

    tree.write("{XML_PATH}")
    print("Updated modules:", updated)
""")

# 1. Create temp script inside pod
subprocess.run(
    ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--",
     "sh", "-c", f"cat > {TMP_SCRIPT} << 'EOF'\n{python_code}\nEOF"],
    check=True
)

# 2. Run the script
subprocess.run(
    ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--",
     "python3", TMP_SCRIPT],
    check=True
)

# 3. Cleanup
subprocess.run(
    ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--",
     "rm", "-f", TMP_SCRIPT],
    check=True
)

print("✔ New module enable flags updated successfully")
