import json
import os
import shutil
from typing import Any, Dict, List, Union

import yaml
import time

import requests
from click.exceptions import Exit
from dotenv import load_dotenv

load_dotenv(dotenv_path='.env')
os.environ['DEMISTO_SDK_IGNORE_CONTENT_WARNING'] = "yes"

from demisto_sdk.commands.init.initiator import Initiator
from demisto_sdk.commands.download.downloader import Downloader
from demisto_sdk.commands.common.tools import parse_marketplace_kwargs

INTEGRATION_INSTANCE_EXCLUDED_FIELDS = ["id", "cacheVersn", "sequenceNumber", "primaryTerm", "modified", "sizeInBytes", "sortValues", "packID", "packName", "itemVersion", "fromServerVersion", "toServerVersion", "definitionId", "prevName", "password", "configvalues", "configtypes", "path", "executable", "cmdline", "hidden", "islongRunning", "remoteSync", "isSystemIntegration", "commandsPermissions", "longRunningId", "incidentFetchInterval", "eventFetchInterval", "assetsFetchInterval", "servicesID", "isBuiltin", "hybrid", "displayPassword", "mappable", "remoteSyncableIn", "remoteSyncableOut", "isFetchSamples", "debugMode"]
JOB_EXCLUDED_FIELDS = ["id", "version", "cacheVersn", "sequenceNumber", "primaryTerm", "modified", "sizeInBytes", "account", "autime", "rawType", "rawName", "status", "custom_status", "resolution_status", "reason", "created", "occurred", "closed", "sla", "investigationId", "attachment", "openDuration", "lastOpen", "closingUserId", "activated", "closeReason", "rawCloseReason", "closeNotes", "dueDate", "reminder", "runStatus", "notifyTime", "rawPhase", "isPlayground", "rawJSON", "parent", "parentXDRIncident", "retained", "category", "rawCategory", "linkedIncidents", "linkedCount", "droppedCount", "sourceInstance", "sourceBrand", "canvases", "lastJobRunTime", "feedBased", "dbotMirrorId", "dbotMirrorInstance", "dbotMirrorDirection", "dbotDirtyFields", "dbotCurrentDirtyFields", "dbotMirrorTags", "dbotMirrorLastSync", "isDebug", "timezoneOffset", "timezone", "scheduledEntryGuid", "minutesToTimeout", "description", "currentIncidentId", "isCurrentIncidentManual", "lastRunTime", "nextRunTime", "displayNextRunTime", "disabledNextRunTime", "schedulingStatus", "previousRunStatus"]
DEMISTO_BASE_URL = os.getenv("DEMISTO_BASE_URL", "")
XSIAM_AUTH_ID = os.getenv("XSIAM_AUTH_ID", "")
DEMISTO_API_KEY = os.getenv("DEMISTO_API_KEY", "")

headers = {
    "x-xdr-auth-id": str(XSIAM_AUTH_ID),
    "Authorization": DEMISTO_API_KEY
}



def verify_dotenv():
    print("\n---Please verify these environment variables:\n")
    print(f"DEMISTO_BASE_URL: {DEMISTO_BASE_URL}")
    print(f"XSIAM_AUTH_ID: {XSIAM_AUTH_ID}")

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


def _call(method: str, path: str, body: Union[dict, None] = None, retries: int = 2) -> (int, Dict[str, Any]):
    """
    Uses the request library to call the XSIAM tenant, passes the JSON data back or raises
    an exception

    :param path: str, path for API endpoint resource
    :param body: dict, body of call
    :return: dict, response body or exception
    """
    for _ in range(retries):
        try:
            response = requests.request(
                method=method,
                url=f"{DEMISTO_BASE_URL}{path}",
                headers=headers,
                json=body,
            )
            if response.status_code in [200, 201]:
                return response.status_code, response.json()

            raise Exception(f"Request to {path} errored: {response.status_code}: {response.text}")

        except Exception as e:
            print(f"Request to {path} errored, retries at {_} {e}")
            if _ == retries - 1:
                return None, None

            time.sleep(15)


def init_empty_package(name: str = "POVContentPack") -> None:
    # Initially set-up the pack structure
    packs_path = os.path.join(os.path.dirname(__file__), "Packs")
    pack_path = os.path.join(packs_path, name)
    if not os.path.exists(packs_path):
        os.makedirs(packs_path)

    # If the Packs/name directory exists, don't initiate the pack again
    if os.path.exists(pack_path):
        return

    try:
        initiator = Initiator(
            marketplace=parse_marketplace_kwargs({"xsiam": True}),
            name=name,
            output=packs_path,
            pack=True,
        )
        initiator.init()

    except Exit as e:
        if e.exit_code != 0:
            raise e

    # Fill in the missing pack structure, removing XSOAR content directories
    xsoar_dirs = [
        "Dashboards",
        "GenericDefinitions",
        "GenericFields",
        "GenericModules",
        "GenericTypes",
        "Jobs",
        "PreProcessRules",
        "Reports",
        "TestPlaybooks",
        "Widgets",
        "Wizards"
    ]
    for d in xsoar_dirs:
        d_path = os.path.join(pack_path, d)
        if os.path.exists(d_path):
            os.rmdir(d_path)

    xsiam_dirs_to_add = [
        "Lists",
        "LayoutRules",
        "LookupData",
        "Triggers"
    ]
    for d in xsiam_dirs_to_add:
        d_path = os.path.join(pack_path, d)
        if not os.path.exists(d_path):
            os.makedirs(d_path)


def download_content_from_sdk(path: str) -> None:
    try:
        Downloader(
            output=path,
            all_custom_content=True,
            auto_replace_uuids=False,
            all_custom_fields=True,
        ).download()
    except Exit as e:
        if e.exit_code != 0:
            raise e


def download_correlations(path: str):
    print("Downloading correlation rules...")
    status_code, json_results = _call(
        method="POST",
        path="/public_api/v1/correlations/get",
        body={
            "request_data": {
                "filters": []
            }
        })

    if json_results:
        results = json_results.get("objects")
        for obj in results:
            obj["global_rule_id"] = obj["name"]

            filename = os.path.join(path, f"{obj['name']}.yml")
            with open(filename, "w") as f:
                yaml.safe_dump(obj, f)

    else:
        print(f"Failure: calling public_api/v1/correlations/get, no objects created.")


def download_dashboards(path: str) -> None:
    print("Downloading dashboards...")
    status_code, json_results = _call(
        method="POST",
        path="/public_api/v1/dashboards/get",
        body={
            "request_data": {
                "filters": []
            }
        })

    if json_results:
        results = json_results.get("objects")

        for obj in results:
            dashboard_name = obj.get("dashboards_data")[0].get("name")
            filename = os.path.join(path, f"{dashboard_name}.json")
            with open(filename, "w") as f:
                json.dump(obj, f)

    else:
        print(f"Failure: calling public_api/v1/dashboards/get, no objects created.")


def download_content_from_api(path: str) -> None:
    remaining_dirs = {
        "CorrelationRules": download_correlations,
        # "LayoutRules": download_layouts,
        "XSIAMDashboards": download_dashboards,
    }

    for directory, function in remaining_dirs.items():
        dir_path = os.path.join(path, directory)
        function(dir_path)


def download_lookup_datasets(path: str) -> List[dict]:
    print("Downloading datasets indices...")
    dir_path = os.path.join(path, "LookupData")

    datasets = []
    status_code, json_results = _call(
        method="POST",
        path="/public_api/v1/xql/get_datasets",
        body={})

    if json_results:
        results = [x for x in json_results.get("reply") if x.get("Type", "").lower() == "lookup"]
        datasets.extend([{
            "dataset_name": x.get('Dataset Name'),
            "dataset_type": "lookup",
            "url": "## FILL MANDATORY FIELD ## - YOU NEED TO UPDATE THIS WITH RAW GITHUB LOCATION OF JSON FILE"
        } for x in results])

    else:
        print(f"Failure: calling public_api/v1/xql/get_datasets, no datasets created.")
        return []

    for dataset in datasets:
        print(f"Fetching data from dataset: {dataset['dataset_name']}")
        status_code, json_results = _call(
            method="POST",
            path="/public_api/v1/xql/lookups/get_data",
            body={
                "request": {
                    "dataset_name": dataset.get("dataset_name"),
                }
            }
        )
        if json_results:
            keys = set(key for d in json_results.get("reply").get("data") for key in d.keys())

            dataset["dataset_schema"] = {k: "## FILL MANDATORY FIELD ## (options: text,number,bool,datetime)" for k in keys}

            # dataset["data"] = json_results.get("reply").get("data")
            path = os.path.join(dir_path, f"{dataset.get('dataset_name')}.json")
            with open(path, "w") as f:
                json.dump(json_results.get("reply").get("data"), f, indent=4)

        else:
            print(f"Failure: calling public_api/v1/xql/lookups/get_data for {dataset.get('dataset_name')}, no data created.")
            dataset["data"] = []

    return datasets


def download_integration_instances(path: str) -> List[dict]:
    print("Downloading integration instances...")
    status_code, json_results = _call(
        method="POST",
        path="/xsoar/public/v1/settings/integration/search",
        body={})

    if json_results:
        results = json_results.get("instances")
        trimming = [instance.pop(x, None) for x in INTEGRATION_INSTANCE_EXCLUDED_FIELDS for instance in results]

        return sorted(results, key=lambda x: x.get("name"))

    else:
        print(f"Failure: calling /xsoar/public/v1/settings/integration/search, no integration instances created.")
        return []


def download_jobs(path: str) -> List[dict]:
    print("Downloading jobs...")
    status_code, json_results = _call(
        method="POST",
        path="/xsoar/public/v1/jobs/search",
        body={})

    if json_results:
        results = json_results.get("data")
        trimming = [instance.pop(x, None) for x in JOB_EXCLUDED_FIELDS for instance in results]

        return sorted(results, key=lambda x: x.get("name"))

    else:
        print(f"Failure: calling /xsoar/public/v1/jobs/search, no integration instances created.")
        return []


def download_marketplace_packs(path: str) -> List[dict]:
    print("Downloading marketplace packs...")
    status_code, json_results = _call(
        method="GET",
        path="/xsoar/public/v1/contentpacks/metadata/installed"
    )

    if json_results:
        results = sorted([{
            "id": x.get("id"),
            "name": x.get("name"),
            "version": x.get("currentVersion")
        } for x in json_results], key=lambda x: x.get("name"))

        return results

    else:
        print(f"Failure: calling /xsoar/public/v1/contentpacks/metadata/installed, no integration instances created.")
        return []


def format_xsoar_config_file(pack_path: str, name: str) -> None:
    xsoar_config = {
        "custom_packs": [
            {
                "id": f"{name}.zip",
                "url": "## FILL MANDATORY FIELD ##",
                "system": "yes"
            }
        ]
    }

    remaining_content = {
        "marketplace_packs": download_marketplace_packs,
        "lookup_datasets": download_lookup_datasets,
        "integration_instances": download_integration_instances,
        "jobs": download_jobs,
    }

    for key, function in remaining_content.items():
        values = function(pack_path)
        xsoar_config[key] = values if values else []

    path = os.path.join(pack_path, "xsoar_config.json")
    with open(path, "w") as f:
        json.dump(xsoar_config, f, indent=4)

    return


def __main__():
    verify_dotenv()
    verify_credentials()

    while True:
        name = input("Enter the name of the pack, (no spaces allowed): ").strip()
        if " " not in name:
            break
        else:
            print("No spaces allowed. Retry...")

    packs_path = os.path.join(os.path.dirname(__file__), "Packs")
    pack_path = os.path.join(packs_path, name)

    init_empty_package(name=name)
    download_content_from_sdk(pack_path)

    download_content_from_api(pack_path)

    format_xsoar_config_file(pack_path, name)

    print(f"------\n"
          f"The pack has been successfully downloaded all content here: {pack_path}\n\n"
          f"A few things you'll need to do: \n"
          f"\t1. Remove all non-necessary content for your package directory\n")

    while True:
        validation = input("Enter 'yes' when you've removed all un-necessary content: ").strip()
        if "yes" == validation:
            break
        else:
            print("Need a 'yes' here. Retry...\n")

    shutil.make_archive(pack_path, "zip", pack_path)

    print(f"\n\nThe demisto-sdk content was properly zipped! \n\nNow for your xsoar_config.json file:\n"
          f"\t1. Remove all non-necessary content for your xsoar_config.json file\n"
          f"\t2. Fill in the 'dataset_schema' for any lookup datasets you push with xsoar_config.json\n"
          f"\t3. Fill in the 'url' for the lookup datasets you push with xsoar_config.json\n"
          f"\t4. If you are updating Marketplace Packs to their latest, change the version to 'latest'\n"
          f"\t5. Once you upload the Pack to a GitHub repo as a .tar or .tar.gz file, add the URL to the `custom_packs` "
          f"in the xsoar_config.json file\n\n"
          )

    print("\n Please note that right now, this must be uplaoded as a non-zipped directory via "
          "`demisto-sdk upload -x -z -i <pack_dir>`")

__main__()
