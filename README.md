# xsiam-pov

Welcome to the XSIAM POV Automation repository. This automation configures the starter POV configuration for a
Cortex XSIAM tenant. The starter configuration content is located in a different repository, such as 
https://github.com/annabarone/xsiam-soc-framework-content.


## (Recommended) Hosted Web Application

The recommended way to run the XSIAM POV Tenant Configurations is by using the hosted POV Companion web application:

https://pov-companion.ts.paloaltonetworks.com/tenant-configurations


## (Developer-Only) Local Environment

#### System Requirements 

* Python 3.9, 3.10 or 3.11.

* git installed.

* A linux, mac or WSL2 machine.

* A Palo Alto Networks XSIAM tenant with Instance Administrator access

### XSIAM Setup

#### Generate API Key

To begin, you need to generate a Standard XSIAM API Key with Instance Administrator roles. 

1. Get your API key by going to the Cortex XSIAM instance and navigating to:
        **Settings > Configurations > Integrations > API Keys**

2. Click the button that says **New Key**

3. Configure your key with the following settings: 

    * **Security Level**: Standard
    * **Role**: Instance Administrator
    * **Enable Expiration Date**: Optional

4. Copy the key

5. Back on the API Key Table page, keep track of your API Key's ID in the table, and the API URL in the top right corner


#### Save API Key as a Credential 

1. In XSIAM, navigate to: 
        **Settings > Configuration > Integrations > Credentials**

2. Click the button that says **New Credential**

3. Configure your credential with the following settings: 

   * **Credential Name**: _Standard XSIAM API Key_
   * **Username**: Your API Key's ID
   * **Password**: Your API Key

**Please Note the Credential Name MUST be _Standard XSIAM API Key_ or else the automations won't work.**

4. Click **Save**.


### Local Python Environment Setup

After git cloning this repository locally, you will need to:

1. Please create a `.env` file in the root directory with the follow values: 

```shell
DEMISTO_BASE_URL=<<<<your API URL>>>>
DEMISTO_API_KEY=<<<<your API Key previously generated>>>>
XSIAM_AUTH_ID=<<<<your API Key ID from API Key Table>>>>
CONTENT_REPO_RAW_LINK=https://raw.githubusercontent.com/Palo-Cortex/soc-optimization/refs/heads/main/xsoar_config.json
```

If you have a different repository with content, please change the CONTENT_REPO_RAW_LINK with your repository's 
`xsoar_config.json`'s GitHub RAW link.

2. Create a python venv with `python -m venv venv`

3. Activate the venv with `source ./venv/bin/activate`

4. Install the requirements with `pip install -r requirements.txt`

#### setup.py Configuration Script

The python setup.py script in this repository will:

* Upload the POVContentPack in the Packs directory 
* Create a Cortex/Core REST API Integration Instance using the credential manually created 
* Trigger a custom alert 
* Grab the alert's ID and output the URL to the alert's workplan

With the previous local environment setup steps completed, you can run the setup script with: 

```shell
python setup.py
```

As a result, a Custom Alert will be created that auto-runs the XSIAM Starter Configuration Setup playbook. This playbook
grabs the configuration from your CONTENT_REPO on GitHub and installs all content there. 


#### removeFramework.py Configuration Script

The python setup.py script in this repository will:

* Delete all custom content regarding the SOC Framework from your tenant
* Delete all POVContentPack content from your tenant 

With the previous local environment setup steps completed, you can run the setup script with: 

```shell
python removeFramework.py
```


#### capture.py Configuration Script

The python capture.py script in this repository will:

* Download all custom content that can be configured with the XSIAM Starter Configuration Setup playbook 
* Format the custom content in demisto-sdk packages and an xsoar_config.json file
* Provide instructions on how to upload the packages to GitHub and utilize in the setup.py script

With the previous local environment setup steps completed, you can run the setup script with: 

```shell
python capture.py
```
