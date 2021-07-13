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

from re import X


try:
  import glob
  import requests
  import json
  import logging
  import re
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
  resp = requests.get(baseurl.rstrip('/') + '/api/public/v1.0' + endpoint, auth = HTTPDigestAuth(publicKey, privateKey), verify = ca_cert_path, cert = key, timeout = 10)
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
      resp = requests.put(baseurl.rstrip('/') + '/api/public/v1.0' + endpoint, auth=HTTPDigestAuth(publicKey, privateKey), verify = ca_cert_path, cert = key, timeout = 10, data = json.dumps(data), headers = header)
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
  # post function to perform POST a payload to a REST API endpoint over HTTPS
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
def post(baseurl, endpoint, data, ca_cert_path, privateKey, publicKey, key = None):
  header = {'Content-Type': 'application/json'}
  # Attempt three times if we have contention
  for i in range(0,2):
    while True:
      resp = requests.post(baseurl.rstrip('/') + '/api/public/v1.0' + endpoint, auth=HTTPDigestAuth(publicKey, privateKey), verify = ca_cert_path, cert = key, timeout = 10, data = json.dumps(data), headers = header)
      if resp.status_code == 200 or resp.status_code == 201:
        return resp
      elif resp.status_code == 409:
        print("Contention issues: %s" % resp.text)
        sleep(randint(1,5))
        continue
      else:
        print("""\033[91mERROR!\033[98m POST response was %s, not `200`\033[m""" % resp.status_code)
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
  addNewAA = False

  if 'agentVersion' not in currentConfig:
    if aaVersion == None:
      for f in glob.glob('/opt/mongodb-mms-automation/versions/mongodb-mms-automation-agent-*'):
        aaVersion = f.split('-')[-1] + "-1"
    # if we do not have an aaVersion here that means it is not installed, so error out
    if aaVersion == None:
      logging.exception("The automation agent does not appear to be installed, please install before continuing")
      raise Exception("The automation agent does not appear to be installed, please install before continuing")

    currentConfig['agentVersion'] = {
      "directoryUrl": opsManagerAddress.rstrip('/') + "/download/agent/automation/",
      "name": aaVersion
    }
    addNewAA = True

  return addNewAA,currentConfig

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
def createProcessMember(fqdn, subDomain, port, replicaSetName, mongoDBVersion, cert_path, horizons = {}, shardedClusterName = None, deploymentType = 'rs'):
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
          "certificateKeyFile": cert_path,
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
  processBaseline['alias'] = fqdn
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

def newHostId(members, replicaSetName):
  if type(members) is not list:
    raise "`members` must be a list"

  # remove non members of this replica set/shard
  reExpression = '^' + replicaSetName + '_' + '.*$'
  regex = re.compile(reExpression)
  filterList = [i for i in members if regex.match(i)]

  filterList.sort()

  # determine the new replica set member name
  if len(filterList) > 0:
    # get the next number in the list
    current = 0
    prev = 0
    for member in filterList:
      exploded = member.split('_')
      try:
        print(exploded[-1])
        if int(exploded[-1]) > (prev + 2):
          newMemberId = replicaSetName + '_' + str(prev + 1)
          break
        else:
          prev = current
          current = int(exploded[-1])
      except ValueError as e:
        continue
    newMemberId = replicaSetName + '_' + str(current + 1)
  else:
    newMemberId = replicaSetName + '_' + str(0)

  return newMemberId


# /
  # checkProcesses determines if a member is already a process, if so it checks it is the same as desired. If it is not the same the process is replaced, if it is missing it is created
def checkProcesses(currentProcess, newProcess, replicaSetName):
  replaceData = True
  memberFound = False
  memberList = []
  currentHost = None

  # check the new member is in the current configuration and determine if the same
  if len(currentProcess) > 0:
    for member in currentProcess:
      # add member to list so we can generate a unique member name if required
      memberList.append(member['name'])
      if member['hostname'] == newProcess['hostname']:
        memberFound = True

        # set the _id to what it currently is
        newProcess['name'] = member['name']
        currentHost = member['name']

        # compare the two objects are the same
        if json.dumps(member, sort_keys = True) != json.dumps(newProcess, sort_keys = True):
          currentProcess.pop(currentProcess.index(member))
        else:
          replaceData = False
          break

  # insert the new member if required
  if replaceData is True and memberFound is False:
    newProcess['name'] = newHostId(members = memberList, replicaSetName = replicaSetName)
    currentHost = newProcess['name']
  if replaceData == True:
    currentProcess.append(newProcess)

  return replaceData,currentProcess,currentHost

def checkReplicaSet(currentReplicaSets, replicaSetName, memberName, memberConfig):
  if type(currentReplicaSets) is not list:
    raise "`currentReplicaSets` must be a list"

  replaceData = True
  replicaSetIds = []
  rsIndex = None
  memberIndex = None
  memberCount= 0

  memberConfig['host'] = memberName

  # Determine if the member is in a replica set
  if len(currentReplicaSets) > 0:
    # go through all the replica seets
    for replicaSets in currentReplicaSets:
      # record the `_id` of each replica set
      logging.debug("Adding replica set to list: %s" % replicaSets['_id'])
      replicaSetIds.append(replicaSets['_id'])
      # if the replica set `_id` matches the desried replica set name we record the element position
      if replicaSets['_id'] == replicaSetName:
        rsIndex = currentReplicaSets.index(replicaSets)
        memberCount = len(replicaSets['members'])
        # find if our member is in the replica set already and remove if so
        for member in replicaSets['members']:
          if member['_id'] == replicaSetName:
            replicaSetPresent = True
          # determine the current member and remove it from the array
          if member['host'] == memberName:
            memberIndex = replicaSets['members'].index(member)
            break
        break

  if rsIndex is None:
    # add replica set skeleton
    currentReplicaSets.append(createReplicaSet(replicaSetName))
    rsIndex = 0
  if memberIndex is None:
    # set the replica set member _id to the legnth of the members array
    memberConfig['_id'] = memberCount
    currentReplicaSets[rsIndex]['members'].append(memberConfig)
  elif rsIndex is not None and memberIndex is not None:
    logging.debug("Replica Set index: %s" % rsIndex)
    logging.debug("Member index: %s" % memberIndex)
    # check if the current member is the same as new member, replace if not
    if json.dumps(currentReplicaSets[rsIndex], sort_keys = True) != json.dumps(memberConfig, sort_keys = True):
      currentReplicaSets[rsIndex]['members'][memberIndex] = memberConfig
    else:
      replaceData = False

  return replaceData,currentReplicaSets

def checkBackups(currentBackup, fqdn, backup = True):
  # Setup the backup agent, if required
  buPresent = None
  replaceBU = False
  for bu in currentBackup:
    if bu['hostname'] == fqdn:
      buPresent = currentBackup.index(bu)
      break
  if backup == True and buPresent == None:
    currentBackup.append({"hostname": fqdn})
    replaceBU = True
  if backup == False and buPresent != None:
    currentBackup.pop(buPresent)
    replaceBU = True

  return replaceBU,currentBackup

def checkMonitoring(currentMonitoring, fqdn, monitoring = False):
  # Setup monitoring agent, if required
  monPresent = None
  replaceMon = False
  for mon in currentMonitoring:
    if mon['hostname'] == fqdn:
      monPresent = currentMonitoring.index(mon)
      break
  if monitoring == True and monPresent == None:
    currentMonitoring.append({"hostname": fqdn})
    replaceMon = True
  if monitoring == False and monPresent != None:
    currentMonitoring.pop(monPresent)
    replaceMon = True

  return replaceMon,currentMonitoring

# /
  # createReplicaSet function to create new replica sets if absent
  #
  # Inputs:
  #   fqdn: the FQDN of the pod, **NOT** the DNS Split Horizon name
  #   replicaSetName: name of the replica set
# /
def checkShard(currentConfig, replicaSetName, shardedClusterName = None, configServer = None):

  shardedClusterPresent = None
  shardPresent = None
  replaceSH = False

  if len(currentConfig) > 0:
    # check if our sharded cluster exists
    for shardedCluster in currentConfig['sharding']:
      if shardedCluster['name'] == shardedClusterName:
        shardedClusterPresent = currentConfig.index(shardedCluster)
        # Check the shard is present
        for replicaSets in shardedCluster['shards']:
          if replicaSets['_id'] == replicaSetName:
            shardPresent = True
            break
  # Create the sharded cluster if it does not exist
  if shardedClusterPresent == None:
    currentConfig.append(createShardedCluster(shardedClusterName, configServer))
    shardedClusterPresent = len(currentConfig) - 1
    replaceSH = True
  # create the shard if not present
  if shardPresent == None:
    currentConfig[shardedClusterPresent]['shards'].append({
      "tags": [],
      "_id": replicaSetName,
      "rs": replicaSetName
    })
    replaceSH = True

  return replaceSH,currentConfig

def checkAlerts(currentAlerts, desiredAlerts):
  # alert settings to check
  checkKeys = [ 'eventTypeName', 'matchers', 'notifications', 'threshold', 'typeName', 'metricThreshold' ]
  newAlerts = []
  updateAlerts = []
  groupId = currentAlerts[0]['groupId']
  replaceAlert = False

  if len(desiredAlerts) > 0:
    for desiredAlert in desiredAlerts:
      if any(currentAlert['eventTypeName'] == desiredAlert['eventTypeName'] for currentAlert in currentAlerts):
          alert = [i for i in currentAlerts if i['eventTypeName'] == desiredAlert['eventTypeName']][0]
          logging.debug("Desired: %s" % desiredAlert)
          for k in checkKeys:
            if k in desiredAlert:
              if json.dumps(alert[k], sort_keys = True) != json.dumps(desiredAlert[k], sort_keys = True):
                updateAlerts.append(dict({'id': alert['id']}, **desiredAlert))
                replaceAlert = True
                break
      else:
        desiredAlert['groupId'] = groupId
        newAlerts.append(desiredAlert)
        replaceAlert = True

  return replaceAlert,newAlerts,updateAlerts

