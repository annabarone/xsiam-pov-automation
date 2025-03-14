import os

import requests
from dotenv import load_dotenv

load_dotenv()

DEMISTO_BASE_URL = os.getenv("DEMISTO_BASE_URL", "")
XSIAM_AUTH_ID = os.getenv("XSIAM_AUTH_ID", "")
DEMISTO_API_KEY = os.getenv("DEMISTO_API_KEY", "")
CONTENT_REPO_RAW_LINK = os.getenv("CONTENT_REPO_RAW_LINK", "")

headers = {
    "x-xdr-auth-id": str(XSIAM_AUTH_ID),
    "Authorization": f"{DEMISTO_API_KEY}"
}


def delete_job(jobId):
    parameters = {}
    response = requests.delete(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/jobs/" + jobId,
        headers=headers,
        json=parameters)

    if response.status_code == 200:
        jobs = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")

    return response


def delete_jobs(jobList):
    for job in jobList:
        parameters = {"query": "name:" + job}
        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/jobs/search",
            headers=headers,
            json=parameters)

        if response.status_code == 200:
            jobs = response.json()
            # Delete Each Job that matches
            for jobID in jobs["data"]:
                print("Deleting Job: " + job)
                delete_job(jobID["id"])
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_datasets(dataSetList):
    for dataset in dataSetList:
        parameters = {
            "request_data": {
                "dataset_name": f"{dataset}",
                "force": "yes"
            }
        }
        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/public_api/v2/xql/delete_dataset",
            headers=headers,
            json=parameters)

        if response.status_code == 200:
            jobs = response.json()
            print("Deleting DataSet: " + dataset)
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_playbook(playbookID):
    parameters = {
        "request_data": {
            "filter": {
                "field": "id",
                "value": str(playbookID)
            }
        }
    }

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/public_api/v1/playbooks/delete",
        headers=headers,
        json=parameters)

    if response.status_code == 200:
        jobs = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")

    return response


def delete_playbooks(playbookLIst):
    for playbook in playbookLIst:
        parameters = {
            "query": playbook
        }
        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/playbook/search",
            headers=headers,
            json=parameters)

        if response.status_code == 200:
            resp = response.json()
            if len(resp['playbooks']) >= 1:
                playbook_id = resp["playbooks"][0]["id"]
                print("Deleting Playbook: " + playbook)
                print("Deleting PlaybookID: " + playbook_id)
                delete_playbook(playbook_id)
            else:
                print("Playbook " + playbook + " does not exist")
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_layout(layoutID):
    parameters = {
        "ids": [str(layoutID)]
    }

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/layout/" + str(layoutID) + "/remove",
        headers=headers,
        json={})

    if response.status_code == 200:
        jobs = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")

    return response


def delete_layouts(layoutList):
    for layout in layoutList:
        parameters = {
            "request_data": {
                "filter": {
                    "field": "name",
                    "value": str(layout)
                }
            }
        }

        response = requests.get(
            url=f"{DEMISTO_BASE_URL}/xsoar/layouts",
            headers=headers,
            json=parameters)

        if response.status_code == 200:
            resp = response.json()
            # print(resp)
            if len(resp) >= 1:
                layout_id = resp[0]["id"]
                print("Deleting Layout: " + layout)
                print("Deleting LayoutID: " + layout_id)
                delete_layout(layout_id)
            else:
                print("Layout " + layout + " does not exist")
        else:
            print(f"Error: {response.status_code} - {response.text}")


if __name__ == '__main__':

    delete_jobs(["Auto Triage", "Collect Playbook Metrics"])

    # delete_datasources([""])
    # delete_integrations([""])
    # delete_classifiers([""])
    # delete_dashboards([""])
    # delete_layouts([""})
    # delete_incidentFields([""])
    # delete_lists([""])

    delete_playbooks(["JOB - Triage Incidents", "JOB - Store Playbook Metrics in Dataset", "Get Alert Tasks and Store to Dataset", "XSIAM Starter Configuration Setup", "Utility - Emergency Alert Resolver", "Use Case - Proofpoint Message Delivered", "Use Case - Proofpoint Click Permitted", "Use Case - Close NGFW Prevented", "Foundation - Upon Trigger", "Close Incidents", "Foundation - Dedup", "Foundation - Enrichment"])

    # delete_scripts([""])
    delete_layouts(["Proofpoint - Click Permitted", "Proofpoint - Message Delivered"])
    delete_datasets(["xsiam_playbookmetrics_raw", "value_tags"])

