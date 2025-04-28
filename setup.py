import json
import os
import time
import webbrowser
from typing import Union

import requests
from click.exceptions import Exit
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')

from demisto_sdk.commands.upload.upload import upload_content_entity

DEMISTO_BASE_URL = os.getenv("DEMISTO_BASE_URL", "")
XSIAM_AUTH_ID = os.getenv("XSIAM_AUTH_ID", "")
DEMISTO_API_KEY = os.getenv("DEMISTO_API_KEY", "")
CONTENT_REPO_RAW_LINK = os.getenv("CONTENT_REPO_RAW_LINK", "")

headers = {
    "x-xdr-auth-id": str(XSIAM_AUTH_ID),
    "Authorization": DEMISTO_API_KEY
}


def verify_dotenv():
    print("\n---Please verify these environment variables:\n")
    print(f"DEMISTO_BASE_URL: {DEMISTO_BASE_URL}")
    print(f"XSIAM_AUTH_ID: {XSIAM_AUTH_ID}")
    print(f"CONTENT_REPO_RAW_LINK: {CONTENT_REPO_RAW_LINK}\n")

    # Ask for confirmation from the user
    confirmation = input("Are these variables expected? (yes/no): ")
    if confirmation.lower().strip() == "yes":
        print("Confirmation received.\n")
    else:
        print("Exiting because the variables were not accepted.\n")
        exit(-1)


def verify_credentials():
    """
    Verify that the "Standard XSIAM API Key" exists in the tenant

    :return: None, exits if incorrect credentials were received.
    """
    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/settings/credentials",
        headers=headers,
        json={})

    if response.status_code == 200:
        json_results = response.json()
        credentials_w_id = [x for x in json_results.get('credentials', []) if x.get('id') == "Standard XSIAM API Key"]
        credentials_w_name = [x for x in json_results.get('credentials', []) if x.get('name') == "Standard XSIAM API Key"]
        if credentials_w_id:
            return
        elif credentials_w_name:
            print("The credential with 'Standard XSIAM API Key' ID was not found in your tenant. You most likely "
                  "renamed your credential. Please delete the credential and recreate it with the correct name.")
        else:
            print("No credentials with 'Standard XSIAM API Key' name were found in your tenant. Please create a "
                  "credential with this name and rerun this script.")
        exit(-2)


def upload_initial_content():

    path = os.path.join(os.path.dirname(__file__), "Packs/POVContentPack")

    try:
        upload_content_entity(
            input=path,
            zip=True,
            xsiam=True,
            insecure=True,
        )
    except Exit as e:
        if e.exit_code != 0:
            raise e


def verify_core_rest_api_values(instance_dict: dict) -> bool:
    # Double check that the "Base marketplace url" defined is correct
    base_marketplace_url = [data for data in instance_dict.get("data", []) if data.get("name") == "marketplace_url"][0].get("value")
    if not base_marketplace_url == "https://marketplace.xsoar.paloaltonetworks.com/content/packs/":
        raise Exception(f"Existing {instance_dict.get('brand')} integration instance not correctly configured. Please "
                        f"disable the existing instance and rerun the automation, or change the 'Base marketplace url' "
                        f"to 'https://marketplace.xsoar.paloaltonetworks.com/content/packs/'.")
    return True


def test_existing_instance(instance_dict: dict) -> bool:
    """
    For a given integration instance, run the test command to verify that the enabled instance works.

    :param instance_dict: dict, integration instance's configuration
    :return: True if "Test" works, False otherwise
    """
    extra_verification = {
        "Core REST API": verify_core_rest_api_values
    }

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/settings/integration/test",
        headers=headers,
        json=instance_dict)

    if response.status_code == 200:
        json_results = response.json()
        test_results = json_results.get("success", "N/A")

        # If test call fails
        if test_results == "N/A":
            raise Exception(f"Testing existing integration instance failed: {test_results.get('message')}")

        # If Integration Instance Test fails
        elif not test_results:
            raise Exception(f"Testing existing {instance_dict.get('brand')} integration instance not successful. Please "
                            f"disable the instance and rerun the automation.")

        elif test_results:
            # For certain integration instances, we may need to double-check something, that's defined here
            if extra_verification.get(instance_dict.get("brand")):
                return extra_verification.get(instance_dict.get("brand"))(instance_dict)
            return True
    else:
        raise Exception(f"Failure when getting integration instances: {response.text}")


def integration_instance_exists(brand: str) -> bool:
    """
    Given a brand, check the tenant for existing, enabled integration instances

    :param brand: str
    :return: True if enabled instance exists, False otherwise
    """
    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/settings/integration/search",
        headers=headers,
        json={})

    if response.status_code == 200:
        json_results = response.json()
        instance_results = json_results.get("instances")

        insts = [x for x in instance_results if x.get('brand') == brand and x.get('enabled') == 'true']
        if len(insts) > 1:
            raise Exception(f"More than one {brand} instance detected: {[x.get('name') for x in insts]}")
        elif len(insts) == 0:
            return False
        elif len(insts) == 1:
            return test_existing_instance(insts[0])
    else:
        raise Exception(f"Failure when getting integration instances: {response.text}")


def create_integration_instances():

    # Grab the Integration Instance Data for POV XSIAM Content Management
    path = os.path.join(os.path.dirname(__file__), "config_files/integration_instances.json")
    with open(path, "r") as f:
        instance_def_list = json.load(f)

    print("Kicking off integration instance creation.")

    # Reset the server URL
    for instance_def in instance_def_list:
        params_list = instance_def["data"]
        server_url_param = [x for x in params_list if x.get("name") == "url"][0]
        server_url_param["value"] = DEMISTO_BASE_URL

        # Verify that there isn't an existing instance that's enabled for this integration
        brand = instance_def.get("brand")
        if brand:
            already_exists = integration_instance_exists(brand)
            if already_exists:
                print(f"Not creating {brand} integration instance because an enabled instance already exists.")
                continue

        # Send integration instance creation request
        response = requests.put(
            url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/settings/integration",
            headers=headers,
            json=instance_def)

        if response.status_code == 200:
            json_results = response.json()
            print(f"Created {brand} integration instance.")
        else:
            if not "already exists" in response.text:
                raise Exception(f"Failure: {response.text}")
            else:
                print("Could not update the existing integraiton instance.")


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
                "pov_github_xsoar_config_file_path": ",".join([CONTENT_REPO_RAW_LINK]),
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
    for x in range(retries):

        # Initially attempt to kick off custom alert -- sometimes errors because initial content isn't registered yet
        # Will retry until custom alert is generated -- if not generated, it'll exit
        for y in range(retries):
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
        for z in range(retries):
            try:
                alert_id = get_alert_id(external_id)
                return alert_id
            except Exception as e:
                if "Couldn't find alert with external" in str(e):
                    print("Waiting for alert to register with XSIAM. Retrying alert search after 30 seconds.")
                    time.sleep(30)
                    continue
                else:
                    print(e)
                    raise e

    raise Exception("Script could not trigger custom alert. XSIAM tenant did not register all custom alerts made.")


def main():
    # Before sending information to the tenant, verify that the correct tenant and credentials are configured
    verify_dotenv()
    verify_credentials()

    # Initial set-up for starter configuration playbook
    upload_initial_content()
    create_integration_instances()
    time.sleep(15)

    # Trigger the alert to actually run the playbook, which configures the XSIAM tenant
    found_alert_id = trigger_playbook()
    url = f"{DEMISTO_BASE_URL.replace('api-', '')}/alerts?action:openAlertDetails={found_alert_id}-workPlan"
    print(f"Alert triggered, view here: {url}")
    webbrowser.open(url)


main()
print("Completed.")
