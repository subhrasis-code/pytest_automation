import os
import subprocess
import textwrap
import logging

logger = logging.getLogger(__name__)

# =============== GLOBAL CONFIG =================
AWS_REGION = "us-west-2"
EKS_CLUSTER = ""
KUBECONFIG_PATH = "/Users/zinnov/Documents/Auto_modules_6_2/test_pulse_data/kubeconfigs/admin.runedge.kubeconfig"
NAMESPACE = "rapid-apps"
SITENAME = "site1"
XML_PATH = f"/opt/rapid4/{SITENAME}/isv_service_config.xml"
TMP_SCRIPT = "/tmp/tmp_xml_edit.py"
# ===============================================


def ensure_kubectl_access():
    os.environ["KUBECONFIG"] = KUBECONFIG_PATH
    logger.info(f"KUBECONFIG set to {KUBECONFIG_PATH}")

    test = subprocess.run(
        ["kubectl", "get", "pods", "-n", NAMESPACE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if test.returncode == 0:
        return

    logger.warning("kubectl access failed. Refreshing AWS SSO credentials...")

    subprocess.run(["aws", "sso", "login"], check=True)
    subprocess.run(
        ["aws", "eks", "update-kubeconfig",
         "--region", AWS_REGION,
         "--name", EKS_CLUSTER],
        check=True
    )

#=================Generic helper to get Kubernetes resources
def get_kube_resource(resource, namespace):
    return subprocess.run(
        ["kubectl", "get", resource, "-n", namespace],
        capture_output=True,
        text=True,
        check=True
    )

#=================Auto-discover the JobManager pod
def get_jobmanager_pod():
    result = get_kube_resource("pods", NAMESPACE)

    for line in result.stdout.strip().split("\n"):
        columns = line.split()
        if len(columns) < 3 or columns[0] == "NAME":
            continue

        pod_name = columns[0]
        pod_status = columns[2]

        if "rapid-jobmanager" in pod_name and pod_status == "Running":
            logger.info(f"Found JobManager pod: {pod_name}")
            return pod_name

    raise RuntimeError("No running rapid-jobmanager pod found")


def run_python_in_pod(python_code: str, POD_NAME):
    """Runs a python snippet inside the pod safely using a temp file"""
    # create temp script
    subprocess.run(
        [
            "kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--",
            "sh", "-c", f"cat > {TMP_SCRIPT} << 'EOF'\n{python_code}\nEOF"
        ],
        check=True
    )

    # execute
    subprocess.run(
        ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--", "python3", TMP_SCRIPT],
        check=True
    )

    # cleanup
    subprocess.run(
        ["kubectl", "exec", POD_NAME, "-n", NAMESPACE, "--", "rm", "-f", TMP_SCRIPT],
        check=True
    )


# =========================================================
# 1️⃣ EMAIL CONFIG
# =========================================================
def update_email_config(new_emails, smtp_config, POD_NAME):
    python_code = textwrap.dedent(f"""
        import xml.etree.ElementTree as ET

        tree = ET.parse("{XML_PATH}")
        root = tree.getroot()

        def set_text(tag, value):
            elem = root.find(".//" + tag)
            if elem is not None:
                elem.text = value

        smtp_config = {smtp_config}
        for k, v in smtp_config.items():
            set_text(k, v)

        email_elem = root.find(".//rapidreceiveemailaddress")
        existing = set()

        if email_elem is not None and email_elem.text:
            existing = set(e.strip() for e in email_elem.text.split(","))

        final_emails = sorted(existing.union(set(new_emails)))
        email_elem.text = ",".join(final_emails)

        tree.write("{XML_PATH}")
        print("[OK] Email configuration updated")
    """)

    run_python_in_pod(python_code, POD_NAME)


# =========================================================
# 2️⃣ LEGACY MODULES
# =========================================================
def update_legacy_modules(legacy_module_config, POD_NAME):
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

    python_code = textwrap.dedent(f"""
        import xml.etree.ElementTree as ET

        tree = ET.parse("{XML_PATH}")
        root = tree.getroot()
        jm = root.find("jobmanager")

        legacy_config = {legacy_module_config}
        legacy_map = {LEGACY_MAP}

        # ---- Update legacy numeric flags ----
        for module, value in legacy_config.items():
            xml_key = legacy_map.get(module)
            if not xml_key:
                continue

            el = jm.find(xml_key)
            if el is not None:
                el.text = "1" if value == 1 else "0"

        # ---- Update <modules><enable> ----
        modules_section = jm.find("modules")
        for mod in modules_section.findall("module"):
            name = mod.findtext("modulename")
            if name in legacy_config:
                enable_tag = mod.find("enable")
                if enable_tag is not None:
                    enable_tag.text = "true" if legacy_config[name] == 1 else "false"

        tree.write("{XML_PATH}")
        print("[OK] Legacy modules updated:", legacy_config)
    """)

    run_python_in_pod(python_code, POD_NAME)



# =========================================================
# 3️⃣ NEW MODULES
# =========================================================
def update_new_modules(new_module_config, POD_NAME):
    python_code = textwrap.dedent(f"""
        import xml.etree.ElementTree as ET

        tree = ET.parse("{XML_PATH}")
        root = tree.getroot()
        jm = root.find("jobmanager")

        module_config = {new_module_config}

        updated = []
        modules_section = jm.find("modules")

        for mod in modules_section.findall("module"):
            name = mod.findtext("modulename")
            if name in module_config:
                enable_tag = mod.find("enable")
                if enable_tag is not None:
                    enable_tag.text = "true" if module_config[name] == 1 else "false"
                    updated.append(f"{{name}}={{enable_tag.text}}")

        tree.write("{XML_PATH}")
        print("[OK] New modules updated:", updated)
    """)

    run_python_in_pod(python_code, POD_NAME)



def main():
    ensure_kubectl_access()
    jobmanager_pod = get_jobmanager_pod()

    # example usage
    run_python_in_pod("print('Hello from JobManager pod')", jobmanager_pod)


    new_emails=["rapid.receive@ischemaview.com"],
    smtp_config={
        "smtpserverip": "email-smtp.us-west-2.amazonaws.com",
        "smtpusername": "AKIA...",
        "smtppassword": "SECRET",
        "smtpport": "587",
        "smtpuseextendedparams": "1",
        "serverip": "127.0.0.1",
        "serverport": "1234"
    }
    # update_email_config(new_emails, smtp_config, jobmanager_pod)


    legacy_modules_config = {
        "PETN": 0,
        "SDH": 1,
        "ASPECTS": 0,
        "RVLV": 1,
    }
    update_legacy_modules(legacy_modules_config, jobmanager_pod)


    new_module_config={
        "OH": 0,
        "MLS": 0,
        "VO": 0,
        "CSPINE": 0,
        "AM": 0,
        "DELTAFUSE": 0,
        "VCF": 0,
        "VOPLUS": 0,
        "ANRTN": 0
    }
    # update_new_modules(new_module_config, jobmanager_pod)

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    main()