# xsiam-pov

Welcome to the XSIAM POV Automation repository. This automation configures the starter POV configuration for a
Cortex XSIAM tenant. The starter configuration content is located in a different repository, such as 
https://github.com/annabarone/xsiam-soc-framework-content.

The python setup script in this repository will:

1. Upload the POVContentPack in the Packs directory 
2. Create a Cortex/Core REST API Integration Instance using the credential manually created 
3. Trigger a custom alert 
4. Grab the alert's ID and output the URL to the alert's workplan

Follow the below steps to run the script: 

### Generate API Key

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


### Save API Key as a Credential 

1. In XSIAM, navigate to: 
        **Settings > Configuration > Integrations > Credentials**

2. Click the button that says **New Credential**

3. Configure your credential with the following settings: 

   * **Credential Name**: _Standard XSIAM API Key_
   * **Username**: Your API Key's ID
   * **Password**: Your API Key

**Please Note the Credential Name MUST be _Standard XSIAM API Key_ or else the automations won't work.**

4. Click **Save**.


### Run Easy Button

1. Please create a `.env` file in the root directory with the follow values: 

```shell
DEMISTO_BASE_URL=<<<<your API URL>>>>
DEMISTO_API_KEY=<<<<your API Key previously generated>>>>
XSIAM_AUTH_ID=<<<<your API Key ID from API Key Table>>>>
CONTENT_REPO_RAW_LINK=http://raw.githubusercontent.com/annabarone/xsiam-soc-framework-content/refs/heads/master/xsoar_config.json
```

If you have a different repository with content, please change the CONTENT_REPO_RAW_LINK with your repository's 
`xsoar_config.json`'s RAW link.


2. Create a python venv with `python -m venv venv`

3. Activate the venv with `source ./venv/bin/activate`

4. Install the requirements with `pip install -r requirements.txt`

5. Run the `setup.py` file with `python setup.py`

As a result, a Custom Alert will be created that auto-runs the XSIAM Starter Configuration Setup playbook. This playbook
grabs the configuration from your CONTENT_REPO on GitHub and installs all content there. 
