# /
  # Functions to deploy replica sets to Ops Manager via the API
  #
  # functions:
  #   get: HTTPS GET method against the Ops Manager REST API
  #   put: HTTPS PUT method against the Ops Manager REST API
  #   add_missing_aa: create the automation agent version section if missing
  #   createProcessMember: function to create a new `processes` member
  #   createReplicaSetMember: function to create a new replica set member
  #   createReplicaSet: function to create a new skeleton replica set config
  #   createShardedCluster: function to create new sharded cluster if absent
  #   findAndReplaceMember: function to determine if member exists in config, create if not, replace if exists. Creates the replica set if missing
# /

try:
  import glob
  import requests
  import json
  import socket
  import sys
  from requests.auth import HTTPDigestAuth
  from random import randint
  from time import sleep
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
  # Attempt three times if we have contention
  for i in range(0,2):
    while True:
      resp = requests.put(baseurl.rstrip('/') + endpoint, auth=HTTPDigestAuth(publicKey, privateKey), verify = ca_cert_path, cert = key, timeout = 10, data = json.dumps(data), headers = header)
      if resp.status_code == 200:
        return resp
      elif resp.status_code == 409:
        print("Contention issues: %s" % resp.text)
        sleep(randint(1,5))
        continue
      else:
        print("""\033[91mERROR!\033[98m PUT response was %s, not `200`\033[m""" % resp.status_code)
        print(resp.text)
        raise requests.exceptions.RequestException

# /
  # add_missing_aa funtion to create the automation agent version section if missing from config.
  #   will look at on disk version of the automation agent to see current installed version and use in config.
  #   Will fail if missing on disk.
  #
  # Inputs:
  #   currentConfig: current configuration for the project
  #   opsManagerAddress: address of Ops Manager, including protocol and port
  #   aaVersion: if you want to force the automation agent version. Optional
  #   
# /
def add_missing_aa(currentConfig, opsManagerAddress, aaVersion = None):
  if 'agentVersion' not in currentConfig:
    if aaVersion == None:
      for f in glob.glob('/opt/mongodb-mms-automation/versions/mongodb-mms-automation-agent-*'):
        aaVersion = f.split('-')[-1] + "-1"
    # if we do not have an aaVersion here that means it is not installed, so error out
    if aaVersion == None:
      raise("The automation agent does not appear to be installed, please install before continuing")

    currentConfig['agentVersion'] = {
      "directoryUrl": opsManagerAddress.rstrip('/') + "/download/agent/automation/",
      "name": aaVersion
    }

  return currentConfig

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
  #   deploymentType: type of member `rs`, `sh`, `cs`, `ms`.
  #   shardedClusterName: Name of the Shard Cluster, required if a member of a sharded cluster
  #   
# /
def createProcessMember(fqdn, subDomain, port, replicaSetName, mongoDBVersion, horizons = {}, shardedClusterName = None, deploymentType = 'rs'):
  if deploymentType == 'ms' and shardedClusterName == None:
    raise Exception("`shardedClusterName` is required if the deploymentType is `ms`")
  if deploymentType == 'ms':
    shardType = {}
    processType = 'mongos'
  elif deploymentType == 'rs':
    shardType = {}
    processType = 'mongod'
  elif deploymentType == 'cs':
    shardType = { "clusterRole": "configsvr"}
    processType = 'mongod'
  elif deploymentType == 'sh':
    shardType = { "clusterRole": "shardsvr"}
    processType = 'mongod'
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
      "sharding": shardType,
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
    "processType": processType
  } 
  processBaseline['alias'] = splitName
  processBaseline['args2_6']['net']['port'] = int(port)
  processBaseline['hostname'] = fqdn
  processBaseline['horizons'] = horizons
  processBaseline['version'] = mongoDBVersion

  # extras for mongod
  if deploymentType in ['rs', 'sh', 'cs']:
    processBaseline['args2_6']['replication']['replSetName'] = replicaSetName
    processBaseline['args2_6']['storage'] = {
      "dbPath": "/data/db",
      "engine": "wiredTiger"
    }
  else:
    processBaseline['cluster'] = shardedClusterName

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
      "chainingAllowed": True,
      "heartbeatTimeoutSecs": 10,
      "catchUpTimeoutMillis": -1,
      "catchUpTakeoverDelayMillis": 30000,
      "electionTimeoutMillis": 10000
    },
    "writeConcernMajorityJournalDefault": "true"
  }
  return basicReplicaSet

# /
  # createShardedCluster function to create new sharded cluster if absent
  #
  # Inputs:
  #   shardedClusterName: name of the of the sharded cluser
  #   configServerReplicaSet: name of the config server replica set
# /
def createShardedCluster(shardedClusterName, configServerReplicaSet):
  baseShardConfig = {
    "shards": [],
    "name": shardedClusterName,
    "configServerReplica": configServerReplicaSet,
    "collections": []
  }

  return baseShardConfig

# /
  # createReplicaSet function to create new replica sets if absent
  #
  # Inputs:
  #   fqdn: the FQDN of the pod, **NOT** the DNS Split Horizon name
  #   replicaSetName: name of the replica set
# /
def findAndReplaceMember(fqdn, replicaSetName, currentConfig, rsMemberConfig, processMemberConfig, monitoring = True, backup = True, shardedClusterName = None, configServer = None, deploymentType = 'rs'):
  if deploymentType not in ['rs','sh','cs', 'ms']:
    raise Exception("`deploymentType` must be either 'rs' for replica set member, 'sh' for shard member, 'cs' for config server member, or 'ms' for mongos")
  if deploymentType == 'ms':
    replicaSetName = 'mongos'

  config = currentConfig
  currentMember = None
  rsMemberName = None
  processMemberName = None
  processMemberList = []
  rsMemberList = []
  replicaSetPresent = None
  replicaSetIds = []
  shardedClusterPresent = None
  shardPresent = None
  shardList = []

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

  if deploymentType != 'ms':

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

    # add to sharded cluster if required (e.g. if not a replica set or not a config server)
    if shardedClusterName != None and deploymentType == 'sh':

      if 'sharding' in config and len(config['sharding']) > 0:
        # check if our sharded cluster exists
        for shardedCluster in config['sharding']:

          if shardedCluster['name'] == shardedClusterName:
            shardedClusterPresent = config['sharding'].index(shardedCluster)

            # Check the shard is present
            for replicaSets in shardedCluster['shards']:
              if replicaSets['_id'] == replicaSetName:
                shardPresent = True
                break
      # Create the sharded cluster if it does not exist
      if shardedClusterPresent == None:
        config['sharding'].append(createShardedCluster(shardedClusterName, configServer))
        shardedClusterPresent = len(config['sharding']) - 1
      # create the shard if not present
      if shardPresent == None:
        config['sharding'][shardedClusterPresent]['shards'].append({
          "tags": [],
          "_id": replicaSetName,
          "rs": replicaSetName
        })

  # Setup the backup agent, if required
  buPresent = None
  for bu in config['backupVersions']:
    if bu['hostname'] == fqdn:
      buPresent = config['backupVersions'].index(bu)
      break
  if backup == True and buPresent == None:
    config['backupVersions'].append({"hostname": fqdn})
  if backup == False and buPresent != None:
    config['backupVersions'].pop(buPresent)

  # Setup monitoring agent, if required
  monPresent = None
  for mon in config['monitoringVersions']:
    if mon['hostname'] == fqdn:
      monPresent = config['monitoringVersions'].index(mon)
      break
  if monitoring == True and monPresent == None:
    config['monitoringVersions'].append({"hostname": fqdn})
  if monitoring == False and monPresent != None:
    config['monitoringVersions'].pop(monPresent)

  return config