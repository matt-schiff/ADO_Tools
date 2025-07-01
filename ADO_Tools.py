# ========================================================================== Library Imports ==========================================================================

import requests
import base64
import time as os_time
import ipaddress
import requests
import urllib3
import json
import os
import sys
import keyboard
from threading import Thread
from datetime import datetime, timedelta, timezone, date, time, UTC
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

# ========================================================================== End Library Imports =========================================================================

# ========================================================================== Script Information ==========================================================================


# Script created by Matt S.

# (c) 2025 Matt Schiff v1.0.0

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# This script ca be used to automate the creation of Jumpboxes and the adding of permissions to tenants based on alerts open in your name. To configure the script, create Personal Access Tokens (PATs) on all ADO dashboards (US, UK, EU, AU, and CA) with READ & WRITE Work Items permissions, and save them as user variables. Additionally, a PAT for spinning up the Jumpboxes and adding permissions to tenants is necessary. This PAT requires a minimum of Read, Write, and Execute permissions for Release, and Read & Execute permissions for Build. [1]
    # Please note that when creating the PATs, you must copy the value provided once the PAT is created, as you will NOT be able to access the value after closing the pop-up and will have to regenerate the token.

# Once configured, the script will pull all MDDR Investigations in your name from each dashboard, collect the URLs, Tenant IDs, and Tenant Regions, and process them to create the appropriate resources. Please note that all jumpbox creation must be performed through the script, or you will experience duplicate boxes being created. This script is still in progress, and updates will occasionally be released as major improvements are made.

# To properly maintain records of jumpservers, a "tenant_regions.json" file will be created in the same directory as the script. This file name is configurable by changing the "data_file_path" variable. This file stores a JSON record of jumpservers that are currently active, and is updated each time the script runs. An example JSON file with masked data can be found in the example.json file.

# PRIOR TO FIRST RUNNING THE SCRIPT:
# 1. Install Python 3.10 or newer from the Windows Store.
# 2. Run the following to download the required software packages:

# pip install requests
# pip install azure.devops
# pip install msrest
# pip install threading

# 3. Add the PATs to your user variables (open instructions file in a web browser for more info)
# 4. Navigate a PowerShell or CMD window to the directory containing the script. (dir, pwd, and cd are your friends)
# 5. Run the script using the following command: python .\{File Name}
    # a. For more information on the tools available in this script, use the -h or --help flag (python .\{File Name} -h)
  
# [1]: Not entirely sure on these permissions, will update once I have confirmation of required permissions.

# Log Levels: 0 - Verbose, 1 - Information, 2 - Warning, 3 - Error (default - 2)

# ======================================================================= End Script Information =======================================================================

# ========================================================================== Global Variables ==========================================================================


# Variables for files needed for functionality
data_file_path = "tenant_regions.json"
log_file_path = "autoclose.log"
config_file_path = "ADO_Tools.config"


# Days of the week for use with datetime.weekday() when determining which alerts to grab
weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# Configuration variables (DEFAULT)
config_options = {}
shifts = {}
log_level = 2
assigned_regions = []

# Configuration variables (CONFIG FILE)
if os.path.exists(config_file_path):
    try:
        with open(config_file_path) as config_file:
            config_options = json.load(config_file)
        for shift in config_options['current_shifts']:
            shift_start = config_options['shifts'][shift]['start_time']
            shift_end = config_options['shifts'][shift]['end_time']
            shift_start = datetime.fromisoformat(date.today().isoformat() + 'T' + shift_start)
            shift_end = datetime.fromisoformat(date.today().isoformat() + 'T' + shift_end)
            if shift_start > shift_end:
                shift_start = shift_start - timedelta(days=1)
            config_options['shifts'][shift]['start_time'] = shift_start
            config_options['shifts'][shift]['end_time'] = shift_end
        today_date = date.today()
        assigned_regions = list(set(config_options['assignments'][weekdays[today_date.weekday()]] + config_options['assignments']['All']))
        shifts = config_options['shifts']
        log_level = config_options['log_level']
    except Exception as e:
        print("Error Parsing config file: ", end="")
        print(e)
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [CRIT]: Error parsing config file: {e}\n")
        exit()

if log_level <= 1:
    with open(log_file_path, 'a') as log_file:
        log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Program Started\n")
        if len(sys.argv) > 1:
            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Flags: {sys.argv[1:]}\n")

# Variables for all PATs needed for script functionality
PIPELINE_PAT= os.environ.get('ADO_PL')
ADO_US_PAT  = os.environ.get('ADO_US')
ADO_UK_PAT  = os.environ.get('ADO_UK')
ADO_EU_PAT  = os.environ.get('ADO_EU')
ADO_AU_PAT  = os.environ.get('ADO_AU')
ADO_CA_PAT  = os.environ.get("ADO_CA")
ADO_IN_PAT  = os.environ.get("ADO_IN")
ADO_AP_PAT  = os.environ.get("ADO_AP")
if PIPELINE_PAT != None and ADO_US_PAT != None and ADO_UK_PAT != None and ADO_EU_PAT != None and ADO_AU_PAT != None and ADO_CA_PAT != None and ADO_IN_PAT != None and ADO_AP_PAT:
    if log_level == 0:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: PATs loaded successfully\n")
else:
    if log_level < 3:
        with open(log_file_path, 'a') as log_file:
            if PIPELINE_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: Pipeline PAT not loaded\n")
            if ADO_US_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: US ADO PAT not loaded\n")
            if ADO_UK_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: UK ADO PAT not loaded\n")
            if ADO_EU_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: EU ADO PAT not loaded\n")
            if ADO_AU_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: AU ADO PAT not loaded\n")
            if ADO_CA_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: CA ADO PAT not loaded\n")
            if ADO_IN_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: IN ADO PAT not loaded\n")
            if ADO_AP_PAT == None:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: AP ADO PAT not loaded\n")

# List of all 30 minute alert Threat Detection Policies. Used to identify high priority alerts.
high_priority_alerts = ['Potential encryption of multiple files', 'Potential ransomware note file was created', 'Immediate pattern detected: user actions resemble ransomware', 'Potential DCSync attack', 'Potential ticket harvesting attack', 'Atypical account connecting directly to a DC']

# Ascii Escape Code to clear screen and move the cursor to the start of the terminal.
clear_screen = '\033[2J\033[;H'

# Header for the script
header = '''     _    ____   ___    _____           _     
    / \\  |  _ \\ / _ \\  |_   _|__   ___ | |___ 
   / _ \\ | | | | | | |   | |/ _ \\ / _ \\| / __|
  / ___ \\| |_| | |_| |   | | (_) | (_) | \\__ \\
 /_/   \\_|____/ \\___/    |_|\\___/ \\___/|_|___/

Created by Matt S.'''

# Variables to identify which flags were used in running the script
alerts_by_analysts_flag = False
closed_alerts_flag = False
shift_handover_flag = False
autoclose_flag = False

#Output for usage with -h/--help flags
help_output = '''Script for automated jumpbox creation created by Matt S. and Drew M. Additonal tools created by Matt S. based on TLDP and Shift Coordinator experiences and needs.

Custom Flags:
    --help (-h): Prints this help message.

Jumpbox creation:
    no flags: Creates Jumpboxes/adds permissions for all currently assigned alerts.
    --pods (-p): Creates Jumpboxes/Adds permissions for all PODS tenants. 
    --addCustomer (-a): Add a customer directly, either with a semicolon separated list (customer_name;customer_id;customer_saas_url;tenant_region) or via input during runtime
    --pipelines (-P): Checks the status of pipelines being run and returns the tenants involved.
    --list (-l): Prints a readable list of all tenants with Jumpboxes or permissions.
    --autoAssign: Automatically assigns alerts and spins up Jumpboxes and permissions as needed.

Reports:
    --alertsByAnalyst (-A): Lists all analysts with alerts and the number of alerts they have assigned.
    --closedAlerts (-c): Lists all analysts with closed alerts during the current shift* and the number of alerts they closed.
    --shiftHandover (-s): Prints all open (new/under investigation) alerts by dashboard
    --autoClose (-C): Prints the number of alerts closed by analysts and autoclose during the current shift* and percentage of alerts closed by autoclose.

*: Current shift or previous shift if ran during the first 30 minutes of an oncoming shift. Logic will need to be updated once the new shift schedule is live.
'''


# Base Query for ADO: All alerts under investigation that are assigned to me.
wiql = {
    "query": "SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.AssignedTo] = @Me AND [System.State] = 'Under Investigation' AND [System.WorkItemType] = 'MDDR Investigation' ORDER BY [Custom.tenant_region] ASC, [Custom.customer_name] ASC"
}



# Dictionary of all high priority customers. Customer information intentionally obfuscated.
PODS_tenants = {
    'd7a4e88b-b0cf-42c7-b8b1-e92e05b3a5f6':
        {
            'region': 'azwu3-prd04',
            'customer_url': 'business.varonis.io',
            'customer_name': 'Company_Name'
        }
    ,
    'fc02aeac-4113-4959-bef6-1e09e2889eb8':
        {
            'region': 'centralus',
            'customer_url': 'techcompany.varonis.io',
            'customer_name': 'Technology Company'
        }
    ,
    '4fa3ce07-0bf6-4ab4-a290-6c94e10185af':
        {
            'region': 'eastus',
            'customer_url': 'university.varonis.io',
            'customer_name': 'Public Institution'
        }
    ,
    'AFEFB67D-836F-4014-9944-A92C301EB9FA':
        {
            'region': 'canadacentral',
            'customer_url': 'manu.varonis.io',
            'customer_name': 'Manufaturing Org'
        }
    ,
    '086907e9-d4b4-4af8-a045-1fdd80195fb2':
        {
            'region': 'azfrc-prd03',
            'customer_url': 'international.varonis.io',
            'customer_name': 'International Conglomerate'
        }
}


# Dictionary of Regions that assigns the region to a specific dashboard.
dashboard_tenants = {
    'us': [],
    'uk': [],
    'eu': [],
    'au': [],
    'ca': [],
    'in': []
}

# All Subregions assigned to their appropriate dashboard dictionary entry.
regions = {
    'azwu3-prd04':   dashboard_tenants['us'],
    'azwu3-prd05':   dashboard_tenants['us'],
    'azcu-prd06':    dashboard_tenants['us'],
    'centralus':     dashboard_tenants['us'],
    'eastus':        dashboard_tenants['us'],
    'eastus2':       dashboard_tenants['us'],
    'uksouth':       dashboard_tenants['uk'],
    'francecentral': dashboard_tenants['eu'],
    'westeurope':    dashboard_tenants['eu'],
    'azfrc-prd03':   dashboard_tenants['eu'],
    'canadacentral': dashboard_tenants['ca'],
    'australiaeast': dashboard_tenants['au'],
    'centralindia':  dashboard_tenants['in']
}

# All Dashboard/Region URLs
organization_urlUS = 'https://dev.azure.com/mddr-us'
organization_urlUK = 'https://dev.azure.com/mddr-uk'
organization_urlEU = 'https://dev.azure.com/mddr-eu'
organization_urlAU = 'https://dev.azure.com/mddr-au'
organization_urlCA = 'https://dev.azure.com/mddr-ca'
organization_urlIN = 'https://dev.azure.com/mddr-in'
organization_urlAP = 'https://dev.azure.com/mddr-ap'

# Dict of all ADO Dashboards, used for auto assigning alerts.
ADO_dict = {
    'US': {
        'url': organization_urlUS,
        'pat': ADO_US_PAT
    },
    'UK': {
        'url': organization_urlUK,
        'pat': ADO_UK_PAT
    },
    'EU': {
        'url': organization_urlEU,
        'pat': ADO_EU_PAT
    },
    'AU': {
        'url': organization_urlAU,
        'pat': ADO_AU_PAT
    },
    'CA': {
        'url': organization_urlCA,
        'pat': ADO_CA_PAT
    },
    'IN': {
        'url': organization_urlIN,
        'pat': ADO_IN_PAT
    },
    'AP': {
        'url': organization_urlAP,
        'pat': ADO_AP_PAT
    }
}

# list of Dicts to provide URL and PAT for each dashboard. Used for threading of alert querying.
ADO_list = [
    {
        'name': 'US',
        'url': organization_urlUS,
        'pat': ADO_US_PAT,
        'alerts': []
    },
    {
        'name': 'UK',
        'url': organization_urlUK,
        'pat': ADO_UK_PAT,
        'alerts': []
    },
    {
        'name': 'EU',
        'url': organization_urlEU,
        'pat': ADO_EU_PAT,
        'alerts': []
    },
    {
        'name': 'AU',
        'url': organization_urlAU,
        'pat': ADO_AU_PAT,
        'alerts': []
    },
    {
        'name': 'CA',
        'url': organization_urlCA,
        'pat': ADO_CA_PAT,
        'alerts': []
    },
    {
        'name': 'IN',
        'url': organization_urlIN,
        'pat': ADO_IN_PAT,
        'alerts': []
    },
    {
        'name': 'AP',
        'url': organization_urlAP,
        'pat': ADO_AP_PAT,
        'alerts': []
    }
]



# ======================================================================== End Global Variables ========================================================================

# ============================================================================= Functions ==============================================================================

'''
Defines shift start time in UTC (01:00 or 13:00) based on the current time

Input: None

Output: Datetime object, current shift start.
'''
def shift_start():
    now = datetime.now(tz=timezone.utc)
    current_shift = datetime.combine(date.today(), time(hour=11), tzinfo=timezone.utc)
    if now.hour < 11 or now.hour > 20:
        current_shift - timedelta(days=1)
    if log_level == 0:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: Current shift {current_shift}\n")
    return current_shift
        

'''
Creates tenants and adds their information to the jump server JSON file.

Input:
  - data_file_path: String of path to JSON file.
  - tenants: Dictionary of all tenants currently open
    Format:
        {
            tenant_id:
                {
                    region: str
                    customer_url: str
                    customer_name: str
                }
        }
        
Output: None
'''
def create_tenants(filepath, tenants_dict, is_silent):
    
    #Check if a new tenant was created
    new_tenant = False
    
    #Create a timestamp for future validation of Jumpbox/Permissions
    today_date = datetime.now(tz=timezone.utc)
    
    #Gather up to date information about existing Jumpbox/Permissions
    json_data = read_tenants(data_file_path)
    parents = []
    add_permissions_list = []
    
    #Check for Tenants with Jumpboxes
    for region, tenants in json_data.items():
        for tenant, values in tenants.items():
            if 'parent' in values:
                parents.append(region)
                break

    #Process new tenants
    for tenant_id, tenant_info in tenants_dict.items():
        region = tenant_info['region']
        url = tenant_info['customer_url']
        name = tenant_info['customer_name']
        #Check if region exists in JSON Data.
        if region in json_data:
            #If Region exists and tenant does not: grant permissions if region has a parent.
            if tenant_id not in json_data[region]:
                json_data[region][tenant_id] = {'creationDate': today_date.isoformat(), 'URL':url, 'Customer Name':name}
                if region in parents:
                    add_permissions_list.append(tenant_id)
                    if log_level == 0:
                        with open(log_file_path, 'a') as log_file:
                            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: Permissions required for {name}:{tenant_id}\n")
            #If Region and Tenant exist: do not grant permissions.
            else:
                pass
            #If Region does not have an open Jumpbox: create one with the tenant.
            if region not in parents:
                json_data[region][tenant_id]['parent'] = True
                parents.append(region)
                if log_level <= 1:
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Creating a new Jumpbox for {name}:{tenant_id}\n")
                create_new_jumpbox(url, tenant_id, name, is_silent)
                new_tenant = True
            #If Region does not exist: create region in JSON and create a Jumpbox with the tenant.
        else:
            json_data[region] = {tenant_id: {'creationDate': today_date.isoformat(), 'URL':url, 'Customer Name':name, 'parent':True}}
            parents.append(region)
            if log_level <= 1:
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Creating a new Jumpbox for {name}:{tenant_id}\n")
            create_new_jumpbox(url, tenant_id, name, is_silent)
            new_tenant = True
            
    #Validate all Regions have a Jumpbox
    while set(parents) != set(list(json_data)):
        #Identify which Region requires a Jumpbox and add one from an existing entry
        for region in list(json_data):
            if region not in parents:
                json_data[region][list(json_data[region])[0]]['parent'] = True
                json_data[region][list(json_data[region])[0]]['creationDate'] = today_date
                parents.append(region)
                if log_level <= 1:
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Creating a new Jumpbox for {name}:{tenant_id}\n")
                create_new_jumpbox(json_data[region][list(json_data[region])[0]]['URL'], list(json_data[region])[0], json_data[region][list(json_data[region])[0]]['Customer Name'], is_silent)
                new_tenant = True
    with open(data_file_path, 'w') as file:
                json.dump(json_data, file, indent=4)
                if log_level == 0:
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: JSON updated\n")
    if len(add_permissions_list) > 0:
        names_list = []
        for tenant in add_permissions_list:
            names_list.append(tenants_dict[tenant]['customer_name'])
        if not is_silent:
            print(format_tenants("Adding permissions for the following tenants", names_list))
        if log_level <= 1:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Adding permissions for {str(names_list)}\n")
        add_permissions(add_permissions_list, is_silent)
        new_tenant = True
    if not new_tenant and not is_silent:
        print("All tenants are currently active.")
        

'''
Reads the JSON into the program. Automatically removes old jump servers from the JSON.

Input: 
  - data_file_path: String, File Path for the JSON file to be read.

Output: dict, information on current Jumpbox and Permissions
    Format:
        {
        REGION:
            {
            TENANT_ID:
                {
                CREATION_DATE: ISO Timestamp
                URL: Str
                NAME: Str
                (OPT) Parent: Bool -- Used to identify which tenant is associated with the region's jumpbox
                }
            }
        }
        
'''   
def read_tenants(data_file_path):
    today_date = datetime.now(tz=timezone.utc)
    offset = timedelta(hours=12)
    if os.path.exists(data_file_path):
        if log_level == 0:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: Tenant JSON file exists. Loading data...\n")
        with open(data_file_path) as file:
            try:
                output = json.load(file)
                filtered_output = {}
                for region, tenants in output.items():
                    filtered_tenants = {}
                    for tenant, value in tenants.items():
                        if datetime.fromisoformat(value['creationDate']) + offset > today_date:
                            filtered_tenants[tenant] = value
                    if len(filtered_tenants) > 0:
                        filtered_output[region] = filtered_tenants
                if log_level == 0:
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: Tenant JSON data loaded\n")
                return filtered_output
            except:
                return {}
    return {}

'''
Runs the pipeline to create a new jumpbox.

Input: 
  - Customer URL: String, URL for customer environment
  - Customer ID: String, GUID for customer
  - Customer Name: String, customer name
  - Is Silent: Bool, prints to command line if not silent

Output: None
'''
def create_new_jumpbox(customer_url, customer_id, customer_name, is_silent):
    organization = "Varonis"
    project = "DevOps"
    pipeline_id = "789"
    url = f"https://dev.azure.com/{organization}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version=6.0-preview.1"
    base64_token = str(base64.b64encode(bytes(':'+PIPELINE_PAT, 'ascii')), 'ascii')

    headers = {
        "Content-Aype": "application/json",
        "Authorization": f"Basic {base64_token}"
    }
    uri_data = {
        "resources": {},
        "templateParameters": {
            "customer_id": customer_id,
            "customer_name": customer_url,
            "access_type": "Basic",
            "reason_for_access": "MDDR"
        },
        "variables": {
            "system.debug": "true"
        }
    }
    try:
        if log_level == 0:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: Requesting Jumpbox for {customer_name}:{customer_id}\n")
        response = requests.post(url, json=uri_data, headers=headers)
        response.raise_for_status()
        if response.json().get('name'):
            if log_level <= 1:
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: New Jumpbox Pipeline {response.json()['name']} created for {customer_name}\n")
        elif log_level < 3:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: Pipeline trigger failed: {response.json()}\n")
        if not is_silent:
            if response.json().get('name'):
                print(f"New Jumpbox Pipeline {response.json()['name']} created for {customer_name}.")
            else:
                print(f"Pipeline trigger failed: {response.json()}.")
    except Exception as e:
        if log_level < 3:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: {str(e)}\n")
        if not is_silent:
            print(str(e))

'''
Adds permissions to any number of customers, recursively reduces list of customers until <15 customers per call

Input: 
  - customer_ids: List[str], IDs of tenants to be added to an existing jumpbox

Output: None
'''
def add_permissions(customer_ids, is_silent):
    if len(customer_ids) > 15:
        if log_level == 0:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: Splitting customer list\n")
        add_permissions(customer_ids[:15], is_silent)
        add_permissions(customer_ids[15:], is_silent)
    else:
        customer_id = ''
        if len(customer_ids) == 0:
            return
        for customer in customer_ids:
            customer_id += customer + ','
        customer_id = customer_id[:-1]
        
        organization = "Varonis"
        project = "DevOps"
        pipeline_id = "1489"
        url = f"https://dev.azure.com/{organization}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version=6.0-preview.1"
        base64_token = str(base64.b64encode(bytes(':'+PIPELINE_PAT, 'ascii')), 'ascii')
        headers = {
            "Content-Aype": "application/json",
            "Authorization": f"Basic {base64_token}"
        }
        uri_data = {
            "resources": {},
            "templateParameters": {
                "customer_id": customer_id,
                "access_type": "Basic",
                "reason_for_access": "MDDR"
            },
            "variables": {
                "system.debug": "true"
            }
        }
        try:
            response = requests.post(url, json=uri_data, headers=headers)
            response.raise_for_status()
            if response.json().get('name'):
                if log_level <= 1:
                    with open(log_file_path, 'a') as log_file:
                        log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Add Permissions Pipeline {response.json()['name']} created for {len(customer_ids)} customers\n")
            elif log_level < 3:
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: Pipeline trigger failed: {response.json()}\n")
            else:
                if response.json().get('name'):
                    print(f"Add Permissions Pipeline {response.json()['name']} created for {len(customer_ids)} customers.")
                else:
                    print(f"Pipeline trigger failed: {response.json()}.")
        except Exception as e:
            if log_level < 3:
                with open(log_file_path, 'a') as log_file:
                        timestamp = datetime.now(timezone.utc).isoformat()
                        log_file.write(f"{timestamp} [WARN]: {str(e)}\n")
            if not is_silent:
                print(f"Error: {str(e)}")

'''
Gets a list of all pipelines currently running for a user and a list of all tenant_ids involved.

Input: None

Output: dict, jumpboxes with the title as the key and list of tenant_ids as the value
'''
def get_active_pipelines():
    now = datetime.now(tz=timezone.utc)
    
    if log_level <= 1:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{datetime.now(tzinfo=timezone.utc).isoformat()} [INFO]: Checking for open pipelines\n")

    pipelines = {}
    organization = "Varonis"
    project = "DevOps"
    base64_token = str(base64.b64encode(bytes(':'+PIPELINE_PAT, 'ascii')), 'ascii')
    headers = {
        "Content-Aype": "application/json",
        "Authorization": f"Basic {base64_token}"
    }
    
    pipeline_id = "1489"
    url = f"https://dev.azure.com/{organization}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version=6.0-preview.1"
    
    response = requests.get(url, headers=headers)
    for run in response.json()['value']:
        if 'Matt Schiff' in run['name']:
            if now - datetime.fromisoformat(run['createdDate']) < timedelta(hours=12):
                if run['state'] != 'completed':
                    pipelines[f"{run['name']} -- {run['id']}"] = []
                    for id in run['templateParameters']['customer_id'].split(','):
                        pipelines[f"{run['name']} -- {run['id']}"].append(id)
    
    pipeline_id = "789"
    url = f"https://dev.azure.com/{organization}/{project}/_apis/pipelines/{pipeline_id}/runs?api-version=6.0-preview.1"
    
    response = requests.get(url, headers=headers)
    for run in response.json()['value']:
        if 'Matt Schiff' in run['name']:
            if now - datetime.fromisoformat(run['createdDate']) < timedelta(hours=12):
                if run['state'] != 'completed':
                    pipelines[f"{run['name']} -- {run['id']}"] = []
                    for id in run['templateParameters']['customer_id'].split(','):
                        pipelines[f"{run['name']} -- {run['id']}"].append(id)
    
    if log_level <= 1:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Found {len(pipelines)} open pipelines\n")
    return pipelines


'''
Pulls a list of the ADO Work Items based on the query provided.

Input: 
  - query: dict, query for ADO
    Format:
        {
            query: str
        }
  - URL: string, URL of the dashboard
  - PAT: string, PAT for the dashboard
  - is_silent: [OPT] supresses command line output

Output: list[dict], a list of dictionaries each representing a single alert.
    Format:
    {
        field_1: value,
        field_2: value,
        ...
        field_n: value
    }

Error: empty list
'''
def get_alerts_from_ADO(query, URL, PAT):   
    try:
        credentials = BasicAuthentication('', PAT)
        connection = Connection(base_url=URL, creds=credentials)
        work_client = connection.clients.get_work_item_tracking_client()
        
        query_result = work_client.query_by_wiql(query).work_items
        
        work_items = []
        if query_result:
            list_query_results = []
            while len(query_result) > 100:
                list_query_results.append(query_result[:100])
                query_result = query_result[100:]
            list_query_results.append(query_result)
            for result in list_query_results:
                work_item_ids = [item.id for item in result]
                alerts = work_client.get_work_items(ids=work_item_ids)
                for i in range(len(work_item_ids)):
                    alerts[i]['System.Id'] = work_item_ids[i]
                work_items += alerts
        return work_items
    except Exception as e:
        print(f"Error fetching alerts for the {URL[-2:].upper()} dashboard")
        print(f"{e}")
        return []

def threaded_get_alerts_from_ADO(query, URL, PAT, return_value):   
    try:
        credentials = BasicAuthentication('', PAT)
        connection = Connection(base_url=URL, creds=credentials)
        work_client = connection.clients.get_work_item_tracking_client()
        
        query_result = work_client.query_by_wiql(query).work_items
        
        work_items = []
        if query_result:
            list_query_results = []
            while len(query_result) > 100:
                list_query_results.append(query_result[:100])
                query_result = query_result[100:]
            list_query_results.append(query_result)
            for result in list_query_results:
                work_item_ids = [item.id for item in result]
                work_items += work_client.get_work_items(ids=work_item_ids)
        return_value += work_items
    except Exception as e:
        print(f"Error fetching alerts for the {URL[-2:].upper()} dashboard")
        print(f"Error message: {e}")

'''
Formats a list of all tenants in a list.

Input:
  - header: str, start of string
  - tenants: list[str], list of customer names

Output: string, formatted string for printing a list of customer names
'''
def format_tenants(header, tenants):
    terminal_size = os.get_terminal_size()
    terminal_width = terminal_size.columns
    tenant_list = ""
    tenant_string = f"{header}: "
    for tenant in sorted(list(set(tenants)), key=str.casefold):
        if len(tenant_string) + len(tenant) + 1 >= terminal_width and len(tenant) < terminal_width:
            if tenant_string.endswith('; '):
                tenant_string = tenant_string[:-1]
            tenant_list += tenant_string + '\n'
            tenant_string = tenant + '; '
        elif len(tenant) > terminal_width:
            if tenant_string.endswith('; '):
                tenant_string = tenant_string[:-1]
            tenant_list += tenant_string + '\n'
            tenant_list += tenant[:terminal_width] + '\n'
            tenant_string = tenant[terminal_width:] + '; '
        else:
            tenant_string += tenant + '; '
    tenant_list += tenant_string[:-2]
    return(tenant_list)

'''
Fetches a list of all alerts associated with the current WIQL query

Input:
  - WIQL_statement: string, WIQL query

Output: dict, keys = dashboards, value = list of alerts
'''
def get_all_alerts(WIQL_statement):
    # Preprocessing info
    all_work_items = {}
    
    # fetch work items by dashboard
    US_work_items = get_alerts_from_ADO(WIQL_statement, organization_urlUS, ADO_US_PAT)
    UK_work_items = get_alerts_from_ADO(WIQL_statement, organization_urlUK, ADO_UK_PAT)
    EU_work_items = get_alerts_from_ADO(WIQL_statement, organization_urlEU, ADO_EU_PAT)
    CA_work_items = get_alerts_from_ADO(WIQL_statement, organization_urlCA, ADO_CA_PAT)
    AU_work_items = get_alerts_from_ADO(WIQL_statement, organization_urlAU, ADO_AU_PAT)
    IN_work_items = get_alerts_from_ADO(WIQL_statement, organization_urlIN, ADO_IN_PAT)
    AP_work_items = get_alerts_from_ADO(WIQL_statement, organization_urlAP, ADO_AP_PAT)

    # Compile all work items into a dictionary by region
    if len(US_work_items) > 0: 
        all_work_items['US'] = US_work_items
    if len(UK_work_items) > 0: 
        all_work_items['UK'] =  UK_work_items
    if len(EU_work_items) > 0: 
        all_work_items['EU'] = EU_work_items
    if len(AU_work_items) > 0: 
        all_work_items['AU'] = AU_work_items
    if len(CA_work_items) > 0: 
        all_work_items['CA'] = CA_work_items
    if len(IN_work_items) > 0: 
        all_work_items['IN'] = IN_work_items
    if len(AP_work_items) > 0:
        all_work_items['AP'] = AP_work_items
    
    return all_work_items
    
def threaded_get_all_alerts(WIQL_statement):
    # Preprocessing:
    all_work_items = {}
    query_threads = []
    
    #Start each thread
    for dashboard in ADO_list:
        dashboard['thread'] = Thread(target=threaded_get_alerts_from_ADO, args=(WIQL_statement, dashboard['url'], dashboard['pat'], dashboard['alerts']))
        dashboard['thread'].start()
    
    #Wait for threads to finish and clean up.
    for dashboard in ADO_list:
        dashboard['thread'].join()
        all_work_items[dashboard['name']] = dashboard['alerts']
        dashboard['alerts'] = []
        dashboard.pop('thread')
    
    return all_work_items
    

'''
Prints the number of alerts by region

Input:
  - all_alerts: dict, key = dashboard, value = list of alerts

Output: None
'''
def print_alerts_by_dashboard(all_alerts):
    dashboards = ['US', 'UK', 'EU', 'AU', 'CA', 'IN', 'AP']
    alert_count = 0
    for dashboard in dashboards:
        dashboard_count = 0
        if dashboard in all_alerts:
            dashboard_count = len(all_alerts[dashboard])
        print(f"{dashboard} Alerts: {dashboard_count}")
        alert_count += dashboard_count
    print(f'\nTotal Work Item Count: {alert_count}')
    print(f'Total Dashboards with Alerts: {len(all_alerts)}\n')


'''
Creates a list of all alerts with details for each alert

Input:
  - all_alerts: list[dict], alerts with all fields

Output: list[dict], alerts with specified fields
'''
def process_alerts(all_alerts):
    alerts = []
    for region, alert_list in all_alerts.items():
        for alert in alert_list:
            fields = alert.fields
            filtered_fields = {
                'tenant_id': fields.get('Custom.tenant_id'),
                'saas_url': fields.get('Custom.customer_saas_url').replace('https://', ''),
                'tenant_region': fields.get('Custom.tenant_region'),
                'customer_name': fields.get('Custom.customer_name'),
                'guid': fields.get('Custom.guid'),
                'changed_date': fields.get('System.ChangedDate'),
                'closed_date': fields.get('Microsoft.VSTS.Common.ClosedDate'),
                'created_date': fields.get('System.CreatedDate'),
                'dashboard': alert.url[27:29].upper(),
                'id': alert.id,
                'threat_detection_policy': fields.get('System.Title')
            }
            try:
                filtered_fields['alert_risk'] = int(fields.get('Custom.alert_risk'))
            except:
                pass
            if 'System.AssignedTo' in fields:
                filtered_fields['assigned_to'] = fields.get('System.AssignedTo')['uniqueName'].split('@')[0]
                filtered_fields['autoclosed'] = 'data' in fields.get('System.AssignedTo')['displayName']
            alerts.append(filtered_fields)
    return(alerts)

'''
Creates a list of dictionaries of all tenants for a given list of processed alerts.

Input:
    - alerts: list[dict], processed alerts
    
Output: list, all tenants in the list of alerts        
'''
def get_tenants(alerts):
    tenants = {}
    for alert in alerts:
        if alert['tenant_id'] not in tenants:
            tenants[alert['tenant_id']] = {'region': alert['tenant_region'], 'customer_url': alert['saas_url'], 'customer_name': alert['customer_name']}
    return tenants

'''
Removes alerts from a list if the alert is not part of the current shift.

Input:
  - alerts: list[dict], processed alerts

Output: list[dict], alerts from current shift
'''
def get_current_alerts(alerts):
    shift_timestamp = shift_start()
    filtered_alerts = []
    for alert in alerts:
        if datetime.fromisoformat(alert['changed_date']) > shift_timestamp:
            filtered_alerts.append(alert)
    return filtered_alerts

'''
Prints the alerts by the analyst assigned

Input:
  - alerts: list[dict], processed alerts

Output: None
'''
def print_alerts_by_analyst(alerts):
    analysts = {}
    total_alerts = 0
    for alert in alerts:
        if 'assigned_to' in alert:
            if alert['assigned_to'] not in analysts:
                analysts[alert['assigned_to']] = 1
            else:
                analysts[alert['assigned_to']] += 1
    analysts = dict(sorted(analysts.items(), key=lambda item: item[1], reverse=True))
    for analyst, num in analysts.items():
        if num > 0:
            print(f"{analyst}: {num} alerts")
            total_alerts += num
    print(f"\nTotal Alerts: {total_alerts}")

'''
Prints a header for the program. Signifies the initialization of script.

Input: None

Output: None
'''
def print_header():
    print(clear_screen, end='')
    print(header)

'''
Assigns an alert to the acting analyst

Input:
  - alert: dict, keys=fields, values=field values

Output: None
'''
def assign_alert(alert):
    # PATCH https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{id}?api-version=7.2-preview.3
    if alert['id'] == None:
        return
    if log_level == 0:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [VERB]: Alert ID: {alert['id']}, Dashboard: {alert['dashboard']}\n")
    dashboard = alert['dashboard']
    URL = ADO_dict[dashboard]['url']
    PAT = ADO_dict[dashboard]['pat']
    changes = [
        {"op": "add", "path": "/fields/System.AssignedTo", "value": "Heet Patel"},
        {"op": "replace", "path": "/fields/System.State", "value": "Under Investigation"}
    ]
    try:
        credentials = BasicAuthentication('', PAT)
        connection = Connection(base_url=URL, creds=credentials)
        work_client = connection.clients.get_work_item_tracking_client()
        updated_work_item = work_client.update_work_item(changes, alert['id'])
        if log_level <= 1:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Assigned alert {updated_work_item.id} to {updated_work_item.fields['System.AssignedTo']['displayName']}\n")
                if alert['alert_risk'] >= 50 or alert['threat_detection_policy'] in high_priority_alerts:
                    log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: !!! Alert {updated_work_item.id} is a high priority alert.\n")
    except Exception as e:
        if log_level < 3:
            with open(log_file_path, 'a') as log_file:
                log_file.write(f"{datetime.now(timezone.utc).isoformat()} [WARN]: Error {str(e)}\n")

'''
Test program, used to check specific code functionality

Input: N/A - Will vary

Output: N/A - Will vary
'''
def test():
    pass
    
#===================================== END Functions ===================================================

# ============================ MAIN Program including all flags ========================================


print_header()
path_taken = False

'''
-h/--help

Prints a help message with all flags and what they do grouped by type of tool.
'''
if '-h' in sys.argv or '--help' in sys.argv:
    print(help_output)
    exit()

'''
-a/--addCustomer

Add a customer directly, either with a semicolon separated list or via input
'''
if '-a' in sys.argv or '--addCustomer' in sys.argv:
    print("Adding new customer to jumpbox.\n")
    index = False
    if '-a' in sys.argv and len(sys.argv) > sys.argv.index('-a') + 1:
        index = sys.argv.index('-a') + 1
    elif '--addCustomer' in sys.argv and len(sys.argv) > sys.argv.index('--addCustomer') + 1:
        index = sys.argv.index('--addCustomer') + 1
        name,id,url,region = sys.argv[sys.argv.index('-a')+1].split(';')
    if index:
        name,id,url,region = sys.argv[index].split(';')
    else:
        name = input("Customer Name:\n > ")
        id = input("Customer ID:\n > ")
        url = input("Customer SaaS URL:\n > ")
        region = input("Tenant Region:\n > ")
    create_tenants(data_file_path, {id:{'region':region,'customer_url':url,'customer_name':name}}, False)
    exit()

'''
No Flags/--getAlerts

Creates Jumpboxes/adds permissions for all currently assigned alerts.
'''
if len(sys.argv) == 1 or '--getAlerts' in sys.argv:
    path_taken = True
    print("\nConfiguring permissions for assigned alerts.\n")
    assigned_alerts = threaded_get_all_alerts(wiql)
    processed_assigned_alerts = process_alerts(assigned_alerts)
    assigned_tenants = get_tenants(processed_assigned_alerts)
    create_tenants(data_file_path, assigned_tenants, False)
    if len(sys.argv) == 1:
        exit()
    
'''
-p/--pods

Create Jumpboxes/adds permissions for all PODS customers as defined in the script.
'''    
if '-p' in sys.argv or '--pods' in sys.argv:
    path_taken = True
    print("\nConfiguring PODS jumpboxes/permissions.\n")
    create_tenants(data_file_path, PODS_tenants, False)

'''
-A/--alertsByAnalyst

Print a list of all analysts with assigned alerts and the number of alerts assigned to each of them.
'''
if '-A' in sys.argv or '--alertsByAnalyst' in sys.argv:
    path_taken = True
    print("\nCurrently Assigned Alerts", end="")
    today = date.today()
    if len(sys.argv) > 2:
        days = 0
        if '-A' in sys.argv:
            if len(sys.argv) > sys.argv.index('-A') + 1:
                try:
                    days = int(sys.argv[sys.argv.index('-A') + 1])
                except ValueError:
                    pass
        else:
            try:
                days = int(sys.argv[sys.argv.index('--alertsByAnalyst') + 1])
            except ValueError:
                pass
        if days > 0:
            today = today - timedelta(days=days)
            print(f" from {today.isoformat()} or older:\n")
        else:
            print(":\n")
    else:
        print(":\n")
    alerts_by_analysts_query = {
        "query": f"SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.State] = 'Under Investigation' AND [System.WorkItemType] = 'MDDR Investigation' AND [System.CreatedDate] <= '{today.isoformat()}' ORDER BY [Custom.tenant_region] ASC, [Custom.customer_name] ASC"
    }
    alerts_by_analysts_alerts = threaded_get_all_alerts(alerts_by_analysts_query)
    processed_alerts_by_analysts_alerts = process_alerts(alerts_by_analysts_alerts)
    print_alerts_by_analyst(processed_alerts_by_analysts_alerts)

'''
-c/--closedAlerts

Print a list of all analysts and number of alerts closed during a shift
'''
if '-c' in sys.argv or '--closedAlerts' in sys.argv:
    path_taken = True
    print(f"\nLast Checked: {datetime.now().strftime('%X')}")
    print("Closed Alerts this shift leaderboard:\n")
    today = date.today()
    closed_alerts_query = {
        "query": f"SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.State] = 'Closed' AND [System.WorkItemType] = 'MDDR Investigation' AND [Microsoft.VSTS.Common.ClosedDate] >= '{today.isoformat()}' AND [System.AssignedTo] Not Contains 'data' ORDER BY [Custom.tenant_region] ASC, [Custom.customer_name] ASC"
    }
    closed_alerts_alerts = threaded_get_all_alerts(closed_alerts_query)
    processed_closed_alerts_alerts = get_current_alerts(process_alerts(closed_alerts_alerts))
    print_alerts_by_analyst(processed_closed_alerts_alerts)

            

'''
-s/--shiftHandover

Prints the number of new/under investigation alerts by dashboard
'''    
if '-s' in sys.argv or '--ShiftHandover' in sys.argv:
    path_taken = True
    print("\nCurrent alerts by dashboard:\n")
    today = date.today()
    if today.month != 1:
        today = today.replace(month=today.month-1)
    else:
        today = today.replace(year=today.year-1)
        today = today.replace(month=12)
    shift_handover_query = {
        "query": f"SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE  [System.WorkItemType] = 'MDDR Investigation' AND ([System.State] = 'Under Investigation' OR [System.State] = 'New') AND [System.CreatedDate] >= '{today.isoformat()}' ORDER BY [Custom.tenant_region] ASC, [Custom.customer_name] ASC"
    }
    shift_handover_alerts = threaded_get_all_alerts(shift_handover_query)
    print_alerts_by_dashboard(shift_handover_alerts)

'''
-C/--autoClose

Prints the number of alerts handled by analysts and Autoclose and the % of alerts Autoclose handled during the current shift
'''    
if '-C' in sys.argv or '--autoClose' in sys.argv:
    path_taken = True
    print("\nAutoclose Statistics:\n")
    autoclose_flag = True
    autoClose = True
    autoclosed_alerts_count = 0
    analyst_closed_alerts_count = 0
    today = date.today()
    now = datetime.now(tz=timezone.utc).time()
    if now > time(hour=1, minute=30) and now < time(hour=4):
        today = today.replace(day=today.day+1)
    autoclose_query = {
        "query": f"SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.State] = 'Closed' AND [System.WorkItemType] = 'MDDR Investigation' AND [Microsoft.VSTS.Common.ClosedDate] >= '{today.isoformat()}' ORDER BY [Custom.tenant_region] ASC, [Custom.customer_name] ASC"
    }
    autoclose_alerts = threaded_get_all_alerts(autoclose_query)
    processed_autoclose_alerts = get_current_alerts(process_alerts(autoclose_alerts))
    for alert in processed_autoclose_alerts:
        if 'autoclosed' in alert:
            if alert['autoclosed']:
                autoclosed_alerts_count += 1
            else:
                analyst_closed_alerts_count += 1
    autoclose_average = autoclosed_alerts_count / (autoclosed_alerts_count+analyst_closed_alerts_count) * 100
    print(f"Autoclosed Alerts: {autoclosed_alerts_count}")
    print(f"Analyst Closed Alerts: {analyst_closed_alerts_count}")
    print(f"Total Closed Alerts: {autoclosed_alerts_count + analyst_closed_alerts_count}\n")
    print(f"Autoclose Average: {round(autoclose_average,2)}%\n")  

'''
-P/--pipelines

Prints the currently running pipelines and the tenants involved.
'''
if '-P' in sys.argv or '--pipelines' in sys.argv:
    path_taken = True
    print("\nChecking for open pipelines.\n")
    tenant_dict = read_tenants(data_file_path)
    pipeline_dict = get_active_pipelines()
    if len(pipeline_dict) == 0:
        print("No open pipelines.")
        exit()
    for pipeline, tenant_ids in pipeline_dict.items():
        print(f"{pipeline}")
        for tenant_id in tenant_ids:
            for region, tenants in tenant_dict.items():
                if tenant_id in tenants:
                    print(f"    {tenants[tenant_id]['Customer Name']}")

'''
-l/--listTenants

Print a list of all tenants currently available to the user
'''
if '-l' in sys.argv or '--listTenants' in sys.argv:
    path_taken = True
    print("\nChecking for open tenants.\n")
    tenants_dict = read_tenants(data_file_path)
    for region, tenants in tenants_dict.items():
        for tenant_id, tenant_info in tenants.items():
            regions[region].append(tenant_info['Customer Name'])
    tenant_exists = False
    for dashboard, dashboard_tenant_list in dashboard_tenants.items():
        if len(dashboard_tenant_list) > 0:
            print(f'{format_tenants(f"{dashboard.upper()} Tenants", dashboard_tenant_list)}\n')
            tenant_exists = True
    if not tenant_exists:
        print("No open tenants.")

'''
--autoAssign

Auto Assigns all alerts in assigned regions every 15ish minutes.
'''
if '--autoAssign' in sys.argv:
    path_taken = True
    if assigned_regions == []:
        exit()
    if log_level <= 1:
        with open(log_file_path, 'a') as log_file:
            log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Assigned Regions: {str(assigned_regions)}\n")
    auto_assign_query = {
        "query": f"""SELECT [System.Id], [System.Title], [System.State] FROM workitems WHERE [System.State] = 'New' AND [System.WorkItemType] = 'MDDR Investigation' AND [System.CreatedDate] >= '{date.today().isoformat()}' AND [Custom.tenant_region] in {str(assigned_regions).replace('[','(').replace(']',')')} ORDER BY [Custom.tenant_region] ASC, [Custom.customer_name] ASC"""
    }
    print('\n')
    while True:
        try:
            print('\033[9;H\033[J', end='')
            current_time = datetime.now(timezone.utc)
            next_check = current_time + timedelta(minutes=5)
            oldest_alert_time = current_time - timedelta(minutes=2)
            print(f'Autoassign last checked: {current_time.astimezone().strftime("%X")}')
            auto_assign_alerts = threaded_get_all_alerts(auto_assign_query)
            processed_auto_assign_alerts = process_alerts(auto_assign_alerts)
            filtered_processed_auto_assign_alerts = []
            if log_level <= 1:
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Checking of dashboards completed\n")
            for alert in processed_auto_assign_alerts:
                if datetime.fromisoformat(alert['created_date']) < oldest_alert_time or alert['threat_detection_policy'] in high_priority_alerts:
                    assign_alert(alert)
                    filtered_processed_auto_assign_alerts.append(alert)
            if log_level <= 1:
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: {len(filtered_processed_auto_assign_alerts)}/{len(processed_auto_assign_alerts)} alerts were autoassigned\n")
            if len(filtered_processed_auto_assign_alerts) > 0:
                auto_assign_tenants = get_tenants(filtered_processed_auto_assign_alerts)
                create_tenants(data_file_path, auto_assign_tenants, True)
            while datetime.now(timezone.utc) < next_check:
                os_time.sleep(30)
        except KeyboardInterrupt:
            if log_level <= 1:
                with open(log_file_path, 'a') as log_file:
                    log_file.write(f"{datetime.now(timezone.utc).isoformat()} [INFO]: Program Terminated\n")
            exit()
    exit()

'''
--test

Stub for testing specific functionality (not used)
'''
if '--test' in sys.argv:
    path_taken = True
    test()

'''
-S/--currentShift

Prints a list of all shifts currently on the clock including all analysts and Team Leads.
'''
if '-S' in sys.argv or '--currentShift' in sys.argv:
    path_taken = True
    current_time = datetime.now(timezone.utc)
    for shift_time, shift in shifts.items():
        if shift['start_time'] < current_time and shift['end_time'] > current_time:
            Print(f"Shift: {shift_time}")
            for analyst in shift['analysts']:
                pass

'''
Confirms the script has done something. If an invalid flag is observed, will print a warning and help output
'''
if not path_taken:
    print("Invalid flag!")
    print(help_output)
