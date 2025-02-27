import json
import os
import time
import webbrowser
from typing import Union

import requests
from click.exceptions import Exit
from demisto_sdk.commands.upload.upload import upload_content_entity
from dotenv import load_dotenv

load_dotenv()

DEMISTO_BASE_URL = os.getenv("DEMISTO_BASE_URL", "")
XSIAM_AUTH_ID = os.getenv("XSIAM_AUTH_ID", "")
DEMISTO_API_KEY = os.getenv("DEMISTO_API_KEY", "")
CONTENT_REPO_RAW_LINK = os.getenv("CONTENT_REPO_RAW_LINK", "")

headers = {
    "x-xdr-auth-id": str(XSIAM_AUTH_ID),
    "Authorization": DEMISTO_API_KEY
}


def upload_initial_content():

    path = os.path.join(os.path.dirname(__file__), "Packs/POVContentPack")

    try:
        upload_content_entity(
            input=path,
            insecure=True,
        )
    except Exit as e:
        if e.exit_code != 0:
            raise e


def create_integration_instances():

    # Grab the Integration Instance Data for POV XSIAM Content Management
    path = os.path.join(os.path.dirname(__file__), "config_files/integration_instances.json")
    with open(path, "r") as f:
        instance_def_list = json.load(f)

    # Reset the server URL
    for instance_def in instance_def_list:
        params_list = instance_def["data"]
        server_url_param = [x for x in params_list if x.get("name") == "url"][0]
        server_url_param["value"] = DEMISTO_BASE_URL

        # Send integration instance creation request
        response = requests.put(
            url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/settings/integration",
            headers=headers,
            json=instance_def)

        if response.status_code == 200:
            json_results = response.json()
        else:
            if not "already exists" in response.text:
                raise Exception(f"Failure: {response.text}")


def get_custom_alerts(external_id):
    """
    Wrapper around "Get all Alerts" XSIAM API Endpoint, used to search for previously created Custom Alert
    https://cortex-panw.stoplight.io/docs/cortex-xsiam-1/78woz98r9h224-get-all-alerts

    :param external_id: XSIAM Alert External ID
    :return:
    """
    data = {
        "request_data": {
            "filters": [
                {
                    "field": "alert_source",
                    "operator": "in",
                    "value": ["Custom Alert"]
                },
                {
                    "field": "external_id_list",
                    "operator": "in",
                    "value": [external_id]
                }
            ],
            "sort": {
                "field": "creation_time",
                "keyword": "asc"
            }
        }
    }

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/public_api/v1/alerts/get_alerts",
        headers=headers,
        json=data)

    if response.status_code == 200:
        json_results = response.json()

        return json_results
    else:
        raise Exception(f"Failure: {response.text}")


def get_alert_id(external_id: str) -> str:
    """
    Takes an XSIAM Alert's external ID and associates it with the XSIAM's ID as seen in the UI

    :param external_id: XSIAM alert external UUID
    :return: XSIAM alert's UI ID
    """
    json_results = get_custom_alerts(external_id)

    alert = [x for x in json_results.get("reply").get('alerts') if external_id == x.get('external_id')]
    if not len(alert) == 1:
        raise Exception(f"Couldn't find alert with external id {external_id}")

    return alert[0].get("alert_id")


def create_custom_alert() -> Union[str, None]:
    """
    Wrapper around "Create a Custom Alert" XSIAM API Endpoint
    https://cortex-panw.stoplight.io/docs/cortex-xsiam-1/7boviliydmbzs-create-a-custom-alert

    :return: UUID string of alert's external ID
    """
    data = {
        "request_data": {
            "alert": {
                "vendor": "PANW POV",
                "product": "PANW POV Starter Configuration",
                "severity": "High",
                "category": "POV",
                "alert_name": "PANW POV Starter Configuration",
                "description": "Starter Configuration Easy Button for XSIAM POV",
                "playbook": "XSIAM Starter Configuration Setup",
                "mitre_defs": {},
                "pov_github_xsoar_config_file_path": CONTENT_REPO_RAW_LINK,
            }
        }
    }

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/public_api/v1/alerts/create_alert",
        headers=headers,
        json=data)

    if response.status_code == 200:
        json_results = response.json()
        external_id = json_results.get("reply")
        print(f"----Custom Alert's External ID: {external_id}")

        return external_id
    else:
        raise Exception(f"Failure: {response.text}")


def trigger_playbook(retries: int=6) -> Union[str, None]:
    external_id = ""

    # Overall custom alert creation retries -- this will loop if an alert was successfully created but the XSIAM tenant
    # doesn't log the alert or register it in a given time
    for _ in range(retries):

        # Initially attempt to kick off custom alert -- sometimes errors because initial content isn't registered yet
        # Will retry until custom alert is generated -- if not generated, it'll exit
        for _ in range(retries):
            try:
                external_id = create_custom_alert()
                break
            except Exception as e:
                if ("The playbook parameter value XSIAM Starter Configuration Setup is invalid" in str(e) or
                        "Invalid parameter names: pov_github_xsoar_config_file_path" in str(e)):
                    print("Waiting for Configuration Playbook to register with XSIAM. Retrying custom alert creation after 90 seconds")
                    time.sleep(90)
                    continue
                else:
                    print(e)
                    raise e

        # Raise exception if no external ID after all retries
        if not external_id:
            raise Exception("Script could not trigger custom alert. The initial content did not register with the "
                            "tenant in time.")

        # Try to correlate the external ID to an alert ID
        for _ in range(retries):
            try:
                alert_id = get_alert_id(external_id)
                return alert_id
            except Exception as e:
                if "Couldn't find alert with external" in str(e):
                    print("Waiting for alert to register with XSIAM. Retrying alert search after 60 seconds.")
                    time.sleep(60)
                    continue
                else:
                    print(e)
                    raise e

    raise Exception("Script could not trigger custom alert. XSIAM tenant did not register all custom alerts made.")


def main():
    upload_initial_content()
    create_integration_instances()
    time.sleep(15)
    found_alert_id = trigger_playbook()
    url = f"{DEMISTO_BASE_URL.replace('api-', '')}/alerts?action:openAlertDetails={found_alert_id}-workPlan"
    print(f"Alert triggered, view here: {url}")
    webbrowser.open(url)


main()
print("Completed.")
