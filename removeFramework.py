import os

import requests
from dotenv import load_dotenv

load_dotenv()

DEMISTO_BASE_URL = os.getenv("DEMISTO_BASE_URL", "")
XSIAM_AUTH_ID = os.getenv("XSIAM_AUTH_ID", "")
DEMISTO_API_KEY = os.getenv("DEMISTO_API_KEY", "")
CONTENT_REPO_RAW_LINK = os.getenv("CONTENT_REPO_RAW_LINK", "")

headers = {"x-xdr-auth-id": str(XSIAM_AUTH_ID), "Authorization": f"{DEMISTO_API_KEY}"}


def delete_job(jobId):
    parameters = {}
    response = requests.delete(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/jobs/" + jobId,
        headers=headers,
        json=parameters,
    )

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
            json=parameters,
        )

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
        parameters = {"request_data": {"dataset_name": f"{dataset}", "force": "yes"}}
        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/public_api/v2/xql/delete_dataset",
            headers=headers,
            json=parameters,
        )

        if response.status_code == 200:
            jobs = response.json()
            print("Deleting DataSet: " + dataset)
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_script(script: str):
    data = {
        "filter": {"query": ""},
        "script": {
            "id": script,
        },
    }

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/automation/delete", headers=headers, json=data
    )

    if response.status_code == 200:
        json_results = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")

    return response


def delete_scripts(script_list: list):
    for script in script_list:
        parameters = {"query": "name:" + script}
        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/automation/search",
            headers=headers,
            json=parameters,
        )

        if response.status_code == 200:
            scripts = response.json()
            # Delete Each Job that matches
            for script_obj in scripts["scripts"]:
                print("Deleting Script: " + script)
                delete_script(script_obj["id"])
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_playbook(playbookID):
    parameters = {"request_data": {"filter": {"field": "id", "value": str(playbookID)}}}

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/public_api/v1/playbooks/delete",
        headers=headers,
        json=parameters,
    )

    if response.status_code == 200:
        jobs = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")

    return response


def delete_playbooks(playbookLIst):
    for playbook in playbookLIst:
        parameters = {"query": playbook}
        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/playbook/search",
            headers=headers,
            json=parameters,
        )

        if response.status_code == 200:
            resp = response.json()
            if len(resp["playbooks"]) >= 1:
                playbook_id = resp["playbooks"][0]["id"]
                print("Deleting Playbook: " + playbook)
                print("Deleting PlaybookID: " + playbook_id)
                delete_playbook(playbook_id)
            else:
                print("Playbook " + playbook + " does not exist")
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_layout(layoutID):
    parameters = {"ids": [str(layoutID)]}

    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/layout/" + str(layoutID) + "/remove",
        headers=headers,
        json={},
    )

    if response.status_code == 200:
        jobs = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")

    return response


def delete_layouts(layoutList):
    for layout in layoutList:
        parameters = {
            "request_data": {"filter": {"field": "name", "value": str(layout)}}
        }

        response = requests.get(
            url=f"{DEMISTO_BASE_URL}/xsoar/layouts", headers=headers, json=parameters
        )

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


def delete_incident_field(incident_field):
    response = requests.delete(
        url=f"{DEMISTO_BASE_URL}/xsoar/incidentfield/{incident_field}",
        headers=headers,
        json={})

    if response.status_code == 200:
        json_results = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")


def delete_incident_fields(incident_fields: list[str]):
    response = requests.get(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/incidentfields",
        headers=headers)
    if response.status_code == 200:
        resp = response.json()
        fields = [x.get("id") for x in resp if x.get('id') in incident_fields]

        for field in fields:
            print("Deleting Incident Field: " + field)
            delete_incident_field(field)
    else:
        print(f"Error: {response.status_code} - {response.text}")


def delete_list(l_id: str):
    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/lists/delete",
        headers=headers,
        json={"id": l_id})

    if response.status_code == 200:
        json_results = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")


def delete_lists(lists: list[str]):
    response = requests.get(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/lists",
        headers=headers)
    if response.status_code == 200:
        resp = response.json()
        lists_to_delete = [x.get("id") for x in resp if x.get('id') in lists]

        for l in lists_to_delete:
            print("Deleting List: " + l)
            delete_list(l)
    else:
        print(f"Error: {response.status_code} - {response.text}")


def delete_dashboards(dashboards: list[str]):
    for dashboard in dashboards:
        print("Deleting Dashboard: " + dashboard)

        data = {
            "request_data": {
                "filters": [
                    {"field": "name", "operator": "EQ", "value": dashboard}
                ]
            }
        }

        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/public_api/v1/dashboards/delete",
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            resp = response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_widgets(widgets: list[str]):
    for widget in widgets:
        print("Deleting Widget: " + widget)

        data = {
            "request_data": {
                "filters": [
                    {"field": "title", "operator": "EQ", "value": widget}
                ]
            }
        }

        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/public_api/v1/widgets/delete",
            headers=headers,
            json=data
        )
        if response.status_code == 200:
            resp = response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_integration(integration: str):
    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/settings/integration-conf/delete",
        headers=headers,
        json={"id": integration})

    if response.status_code == 200:
        json_results = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")


def delete_integrations(integrations: list[str]):
    response = requests.get(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/settings/integration-commands",
        headers=headers)
    if response.status_code == 200:
        resp = response.json()
        integrations_to_delete = [x.get("id") for x in resp if x.get('name') in integrations]

        for integration in integrations_to_delete:
            print("Deleting Integrations: " + integration)
            delete_integration(integration)
    else:
        print(f"Error: {response.status_code} - {response.text}")



def delete_instance(instance_id: str):
    response = requests.delete(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/settings/integration/{instance_id}",
        headers=headers)

    if response.status_code == 200:
        json_results = response.json()
    else:
        print(f"Error: {response.status_code} - {response.text}")


def delete_integration_instances(instances: list[str]):
    response = requests.post(
        url=f"{DEMISTO_BASE_URL}/xsoar/public/v1/settings/integration/search",
        headers=headers,
        json={})

    if response.status_code == 200:
        resp = response.json()
        instances_to_delete = [x.get('id') for x in resp.get('instances') if x.get('name') in instances]

        for inst in instances_to_delete:
            print("Deleting Integration Instance: " + inst)
            delete_instance(inst)
    else:
        print(f"Error: {response.status_code} - {response.text}")


def delete_correlation_rules(correlation_rules: list[str]):
    for rule in correlation_rules:
        response = requests.post(
            url=f"{DEMISTO_BASE_URL}/public_api/v1/correlations/delete",
            headers=headers,
            json={
                "request_data": {
                    "filters": [
                        {"field": "name", "operator": "EQ", "value": rule}
                    ]
                }
            }
        )

        if response.status_code == 200:
            resp = response.json()
        else:
            print(f"Error: {response.status_code} - {response.text}")


def delete_soc_content():
    delete_jobs(["Auto Triage", "Collect Playbook Metrics"])

    # delete_correlation_rules([
    #     ""
    # ])
    delete_integration_instances([
        "PlaybookMetrics",
        "Whois_instance_1"
    ])
    delete_widgets([
        "Common Use Cases",
        "Time Saved by XSIAM per Task",
        "Total FTEs Saved",
        "Total SOC Hours Worked by XSIAM",
        "Time Save by Category",
        "Tools used by XSIAM by Hour",
        "XSIAM Vendor Usage",
        "Total Alerts",
        "Alerts Auto Resolved",
        "Total Incidents after Grouping",
        "Analysts Incidents",
        "Total Alerts By Source",
        "Custom Scripts Usage"
    ])
    # delete_classifiers([""])
    delete_dashboards(["XSIAM SOC Value Metrics"])
    # delete_layouts([""})
    # delete_incident_fields([
    #     ""
    # ])
    delete_lists([
        "Job_Utility_Bulk_Alert_Closer_ID_List",
        "Assets_Type",
        "SOCOptimizationConfig",
        "ProductionAssets"
    ])
    delete_playbooks([
        "JOB - Triage Incidents",
        "JOB - Store Playbook Metrics in Dataset",
        "Get Alert Tasks and Store to Dataset",
        "Utility - Emergency Alert Resolver",
        "Foundation - Upon Trigger",
        "Close Incidents",
        "Foundation - Dedup",
        "Foundation - Error Handling",
        "Foundation - Enrichment",
        "Foundation - Load Configuration"
    ])
    delete_scripts([
        "CloseAlerts"
    ])
    # delete_layouts([
    #     ""
    # ])
    delete_datasets([
        "xsiam_playbookmetrics_raw",
        "value_tags"
    ])


def delete_config_automation_content():
    delete_integration_instances([
        "POV XSIAM Content Management Instance"
    ])
    delete_integrations([
        "POV XSIAM Content Management"
    ])
    delete_incident_fields([
        "incident_correlationrulescreated",
        "incident_dashboardscreated",
        "incident_integrationinstancescreated",
        "incident_lookupdatasetscreated",
        "incident_povgithubxsoarconfigfilepath",
    ])
    delete_playbooks([
        "XSIAM Starter Configuration Setup",
    ])
    delete_scripts([
        "CorrelationRuleCreator",
        "DashboardCreator",
        "ExtendedConfigurationSetup",
        "IntegrationInstanceCreator",
        "LookupDatasetCreator",
        "POVInstallContentBundle",
        "POVJobCreator",
        "POVListCreator",
        "XSIAMContentPackInstaller",
    ])


def delete_threat_intel():
    delete_integration_instances([
        "abuse.ch SSL Blacklist Feed_instance_1",
        "Blocklist_de Feed_instance_1",
        "BruteForceBlocker Feed_instance_1",
        "FeedURLhaus_instance_1",
        "Feodo Tracker IP Blocklist Feed_instance_1",
        "LOLBAS Feed_instance_1",
        "MalwareBazaar Feed_instance_1",
        "MITRE ATT&CK v2_instance_1",
        "SpamhausFeed_instance_1",
        "TeamCymru_instance_1",
        "ThreatFox Feed_instance_1",
        "Tor Exit Addresses Feed_instance_1",
        "Whois_instance_1"
    ])


if __name__ == "__main__":
    delete_soc_content()
    # delete_threat_intel()
    # delete_config_automation_content()
