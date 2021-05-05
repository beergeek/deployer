# /
  # Functions to deploy replica sets to Ops Manager via the API
  #
  # functions:
  #   get: HTTPS GET method against the Ops Manager REST API
  #   put: HTTPS PUT method against the Ops Manager REST API
  #   createProcessMember: function to create a new `processes` member
  #   createReplicaSetMember: function to create a new replica set member
  #   createReplicaSet: function to create a new skeleton replica set config
  #   findAndReplaceMember: function to determine if member exists in config, create if not, replace if exists. Creates the replica set if missing
# /

try:
  import requests
  from requests.auth import HTTPDigestAuth
  import json
  import copy
  import socket
  import sys
except ImportError as e:
  print(e)
  exit(1)

# /
  # get function to perform GET calls to a REST API endpoint over HTTPS
  #
  # Inputs:
  #   baseurl: The URL for Ops Manager, including the base API, e.g. `htts://ops-manager.gov.au:8443/api/public/v1.0`
  #   endpoint: The desired endpoint starting with a slash, e.g. `/groups/{PROJECT-ID}/automationConfig`
  #   ca_cert_path: The absolute path, including file name, of the CA certificate
  #   privateKey: The private key portion of the Ops Manager API Access Key
  #   publicKey: The public key portion of the Ops Manager API Access Key
  #   key: The absolute path to the combined private key and X.509 certificate. OPTIONAL
# /
def get(baseurl, endpoint, ca_cert_path, privateKey, publicKey, key = None):
  resp = requests.get(baseurl.rstrip('/') + endpoint, auth = HTTPDigestAuth(publicKey, privateKey), verify = ca_cert_path, cert = key, timeout = 10)
  if resp.status_code == 200:
    group_data = json.loads(resp.text)
    return group_data
  else:
    print("""\033[91mERROR!\033[98m GET response was %s, not `200`\033[m""" % resp.status_code)
    print(resp.text)
    raise requests.exceptions.RequestException

# /
  # put function to perform PUT a payload to a REST API endpoint over HTTPS
  #
  # Inputs:
  #   baseurl: The URL for Ops Manager, including the base API, e.g. `htts://ops-manager.gov.au:8443/api/public/v1.0`
  #   endpoint: The desired endpoint starting with a slash, e.g. `/groups/{PROJECT-ID}/automationConfig`
  #   data: JSON paylod to upload
  #   ca_cert_path: The absolute path, including file name, of the CA certificate
  #   privateKey: The private key portion of the Ops Manager API Access Key
  #   publicKey: The public key portion of the Ops Manager API Access Key
  #   key: The absolute path to the combined private key and X.509 certificate. OPTIONAL
# /
def put(baseurl, endpoint, data, ca_cert_path, privateKey, publicKey, key = None):
  header = {'Content-Type': 'application/json'}
  resp = requests.put(baseurl.rstrip('/') + endpoint, auth=HTTPDigestAuth(publicKey, privateKey), verify = ca_cert_path, cert = key, timeout = 10, data = json.dumps(data), headers = header)
  if resp.status_code == 200:
    return resp
  else:
    print("""\033[91mERROR!\033[98m PUT response was %s, not `200`\033[m""" % resp.status_code)
    print(resp.text)
    raise requests.exceptions.RequestException

# /
  # createProcessMember funtion to create a new process member
  #
  # Inputs:
  #   fqdn: FQDN of the pod
  #   subDomain: the subdomain to use for the DNS Split Horizon, e.g. pace-pst
  #   port: port that Mongod will listen on
  #   mongoDBVersion: The mongoDB Version, e.g. `4.4.5-ent`
  #   horizons: an object of horizon names and single resolvable addresses to use for discovery outside of OpenShift, e.g {'OUTSIDE': 'mongodb-pace-pst-dca-cd-0.subdomain.whatever.com'}. OPTIONAL
  #   replicaSetName: name of the replica set
# /
def createProcessMember(fqdn, subDomain, port, replicaSetName, mongoDBVersion, horizons = {}):
  # Create the DNS Split Horizon name
  splitName = fqdn.split('.')[0] + '.' + subDomain

  processBaseline = {
    "args2_6": {
      "net": {
        "bindIp": "0.0.0.0",
        "tls": {
          "mode": "requireTLS",
          "certificateKeyFile": "/data/pki/server.pem",
          "disabledProtocols": "TLS1_0,TLS1_1"
        }
      },
      "replication": {
      },
      "security": {
        "clusterAuthMode": "x509"
      },
      "setParameter": {
        "ocspEnabled": False
      },
      "sharding": {},
      "storage": {
        "dbPath": "/data/db",
        "engine": "wiredTiger"
      },
      "systemLog": {
        "destination": "file",
        "path": "/var/log/mongodb-mms-automation/mongodb.log"
      }
    },
    "authSchemaVersion": 5,
    "directAttachShouldFilterByFileList": False,
    "disabled": False,
    "featureCompatibilityVersion": "4.4",
    "logRotate": {
      "sizeThresholdMB": 1000,
      "timeThresholdHrs": 24
    },
    "manualMode": False,
    "processType": "mongod"
  } 
  processBaseline['alias'] = splitName
  processBaseline['args2_6']['net']['port'] = int(port)
  processBaseline['args2_6']['replication']['replSetName'] = replicaSetName
  processBaseline['hostname'] = fqdn
  processBaseline['horizons'] = horizons
  processBaseline['version'] = mongoDBVersion

  return processBaseline

# /
  # createReplicaSetMember function to create new replica set members. Can be for new or modified
  #
  # Inputs:
  #   priority: priority of this member, defaults to `1`
  #   arbiter: Boolean to determine if member is an aribter, default is `False`
  #   horizons: an object of horizon names and single resolvable addresses to use for discovery outside of OpenShift, e.g {'OUTSIDE': 'mongodb-pace-pst-dca-cd-0.subdomain.whatever.com'}
  #   replicaSetName: name of the replica set
# /
def createReplicaSetMember(replicaSetName, priority = 1, arbiter = False, horizons = {}):
  if arbiter == True:
    priority = 0
  replicaSetMember = {
      "arbiterOnly": arbiter,
      "buildIndexes": True,
      "hidden": False,
      "priority": priority,
      "slaveDelay": 0,
      "tags": {},
      "votes": 1,
      "horizons": horizons
    }

  return replicaSetMember

# /
  # createReplicaSet function to create new replica sets if absent
  #
  # Inputs:
  #   replicaSetName: name of the replica set
# /
def createReplicaSet(replicaSetName):
  basicReplicaSet = {
    "_id": replicaSetName,
    "members": [],
    "protocolVersion": "1",
    "settings": {
      "catchUpTakeoverDelayMillis": 30000,
      "catchUpTimeoutMillis": -1,
      "chainingAllowed": True,
      "electionTimeoutMillis": 10000,
      "getLastErrorDefaults": {
        "w": "majority",
        "wtimeout": 0
      },
      "getLastErrorModes": {},
      "heartbeatTimeoutSecs": 10
    },
    "writeConcernMajorityJournalDefault": "true"
  }
  return basicReplicaSet

# /
  # createReplicaSet function to create new replica sets if absent
  #
  # Inputs:
  #   fqdn: the FQDN of the pod, **NOT** the DNS Split Horizon name
  #   replicaSetName: name of the replica set
# /
def findAndReplaceMember(fqdn, replicaSetName, currentConfig, rsMemberConfig, processMemberConfig, monitoring = True, backup = True):
  # deciding if I should do a proper copy
  config = copy.deepcopy(currentConfig)
  currentMember = None
  rsMemberName = None
  processMemberName = None
  processMemberList = []
  rsMemberList = []
  replicaSetPresent = None
  replicaSetIds = []

  # determine if the member is already in the deployment
  if 'processes' in config and len(config['processes']) > 0:
    for member in config['processes']:
      # add member to list so we can generate a unique member name if required
      processMemberList.append(member['name'])
      if member['hostname'] == fqdn:
        processMemberName = member['name']
        currentMember = member['name']
        config['processes'].pop(config['processes'].index(member))
  processMemberList.sort()

  # add member
  if currentMember == None and len(processMemberList) > 0:
    processMemberConfig['name'] = replicaSetName + '_' + str(int(processMemberList[-1].split('_')[-1]) + 1)
  elif currentMember == None:
    processMemberConfig['name'] = replicaSetName + '_0'
  else:
    processMemberConfig['name'] = processMemberName
  config['processes'].append(processMemberConfig)

  # Determine if the member is in a replica set
  if 'replicaSets' in config and len(config['replicaSets']) > 0:

    # go through all the replica seets
    for replicaSets in range(len(config['replicaSets'])):

      # record the `_id` of each replica set
      replicaSetIds.append(config['replicaSets'][replicaSets]['_id'])

      # if the replica set `_id` matches the desried replica set name we record the element position
      if config['replicaSets'][replicaSets]['_id'] == replicaSetName:
        replicaSetPresent = replicaSets

        # find if our member is in the replica set already and remove if so
        for member in range(len(config['replicaSets'][replicaSets]['members'])):
          rsMemberList.append(config['replicaSets'][replicaSets]['members'][member]['_id'])

          # determine the current member and remove it from the array
          if config['replicaSets'][replicaSets]['members'][member]['host'] == currentMember:
            rsMemberName = config['replicaSets'][replicaSets]['members'][member]['_id']
            config['replicaSets'][replicaSets]['members'].pop(member)
    rsMemberList.sort()
  else: 
    # add replica set skeleton
    rsConfig = createReplicaSet(replicaSetName)
    config['replicaSets'].append(rsConfig)
    replicaSetPresent = 0
  
  if replicaSetPresent == None:
    # add replica set skeleton
    replicaSetPresent = len(replicaSetIds)
    rsConfig = createReplicaSet(replicaSetName)
    config['replicaSets'].append(rsConfig)

  # add member
  if rsMemberName == None and len(rsMemberList) > 0:
    rsMemberConfig['_id'] = int(rsMemberList[-1] + 1)
  elif rsMemberName == None:
    rsMemberConfig['_id'] = 0
  else:
    rsMemberConfig['_id'] = rsMemberName
  rsMemberConfig['host'] = processMemberConfig['name']
  # add replica set member to replica set
  config['replicaSets'][replicaSetPresent]['members'].append(rsMemberConfig)

  # Setup the backup agent, if required
  if backup == True:
    buPresent = False
    for bu in config['backupVersions']:
      if bu['hostname'] == fqdn:
        buPresent = True
        break
    if buPresent == False:
      config['backupVersions'].append({"hostname": fqdn})

  # Setup monitoring agent, if required
  if monitoring == True:
    monPresent = False
    for mon in config['monitoringVersions']:
      if mon['hostname'] == fqdn:
        monPresent = True
        break
    if monPresent == False:
      config['monitoringVersions'].append({"hostname": fqdn})

  return config