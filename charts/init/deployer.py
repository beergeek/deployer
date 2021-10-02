try:
  from datetime import datetime
  import json
  import omCommon
  import os
  import re
  import logging
  import socket
  import sys
  import yaml
  from time import sleep
  from os import getenv
except ImportError as e:
  print(e)
  exit(1)

# Check the configuration for validity
def configChecker(iConfig):
  iConfig['fqdn'] = socket.getfqdn()
  iConfig['hostname'] = iConfig['fqdn'].split('.')[0]
  iConfig['splitName'] = iConfig['hostname'] + '.' + iConfig['subDomain']
  #iConfig[''] = iConfig['splitName'] + '.' + iConfig['dnsSuffix'] + ':' + str(iConfig['port'])
  hostSplit = iConfig['fqdn'].split('.')
  hostBase =  hostSplit[0].split('-')
  if int(hostBase[-1]) == 0:
    iConfig['firstPod'] = True
  else:
    iConfig['firstPod'] = False
  iConfig['horizon'] = iConfig['outsideName'] + ':' + str(int(iConfig['outsidePort']) + int(hostBase[-1]))
  if 'priority' in iConfig and iConfig['hostname'] in iConfig['priority']:
    iConfig['priority'] = iConfig['priority'][iConfig['hostname']]
  else:
    iConfig['priority'] = 1
  if 'arbiter' in iConfig and iConfig['hostname'] in iConfig['arbiter']:
    iConfig['arbiter'] = True
  else:
    iConfig['arbiter'] = False
  if 'nonBackupAgent' in iConfig and iConfig['hostname'] in iConfig['nonBackupAgent']:
    iConfig['backup'] = False
  else:
    iConfig['backup'] = True
  if 'nonMonitoringAgent' in iConfig and iConfig['hostname'] in iConfig['nonMonitoringAgent']:
    iConfig['monitoring'] = False
  else:
    iConfig['monitoring'] = True
  if 'shardedClusterName' not in iConfig:
    iConfig['shardedClusterName'] = None
  if 'configServerReplicaSet' not in iConfig:
    iConfig['configServerReplicaSet'] = None
  if 'deploymentType' not in iConfig:
    iConfig['deploymentType'] = 'rs'
  elif iConfig['deploymentType'] not in ['rs','sh','cs', 'ms']:
    raise Exception("`deploymentType` must be either 'rs' for replica set member, 'sh' for shard member, 'cs' for config server member, or 'ms' for mongos")
  if iConfig['deploymentType'] == 'ms':
    iConfig['replicaSetName'] = None
  if 'replicaSetName' not in iConfig:
    raise Exception("The replica set/shard name must be included in the `replicaSetName` parameter")
  if 'requireAlerts' not in iConfig:
    iConfig['requiredAlerts'] = None

  return iConfig

def getEnvData(iConfig):
  try:
    iCfg = {}
    iCfg.update({'omBaseUrl': os.getenv('MMSBASEURL'), 'publicKey': os.getenv('APIPUB'), 'privateKey': os.getenv('APIKEY'), 'projectID': os.getenv('MMSGROUPID'), 'mongoDBVersion': os.getenv('VERSION'), 'outsideName': os.getenv('HORIZONADDR'), 'outsidePort': os.getenv('HORIZONPORT')})
    iCfg.update({'ca_cert_path': iConfig['net']['tls']['CAFile'], 'port': iConfig['net']['port'], 'replicaSetName': iConfig['replication']['replSetName'], 'cert_path': iConfig['net']['tls']['certificateKeyFile']})
    return iCfg
  except ValueError as e:
    raise Exception('Failure to get environment variables')

def main():
    iDeployConfig = {}
    iDeployConfig.update({'dnsSuffix': 'mongodb.local','subDomain': 'test'})
    # Determine logging level
    if getenv('LOGLEVEL').upper() == 'DEBUG':
      logLevel = logging.DEBUG
    else:
      logLevel = logging.INFO
    logging.basicConfig(format='{"ts": "%(asctime)s, "f": "%(funcName)s", "l": %(lineno)d, "msg": "%(message)s"}', level=logLevel)

  #try:
    if os.path.isfile('/init/mongod.conf') is False:
      print("\033[91mERROR!\033[0;0m The `mongod.conf` file must be in the same directory as `deployer.py`")
      raise Exception("\033[91mERROR!\033[0;0m The `mongod.conf` file must be in the same directory as `deployer.py`")

    iCfg = {}
    with open('/init/mongod.conf', 'r') as f:
      iCfg = yaml.safe_load(f)
      f.close()
    logging.debug(iCfg)

    iDeployConfig.update(getEnvData(iCfg))

    # check input
    iDeployConfig = configChecker(iConfig = iDeployConfig)
    logging.debug(iDeployConfig)
    logging.debug("\033[91m%s\033[0;0m" % iDeployConfig['horizon'])

    # get current alerts if this is the first pod (e.g. only do this once)
    # code for alerts
    if iDeployConfig['firstPod'] is True:

      if os.path.isfile('/init/alerts.json') is True:
        with open('/init/alerts.json', 'r') as f:
          iDeployConfig.update(json.load(f))
          f.close()

        iDeployConfig.update({'alerts': []})
        logging.debug("Getting Alerts...")
        currentAlerts = omCommon.get(baseurl = iDeployConfig['omBaseUrl'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/alertConfigs',
          publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])
  
        logging.debug(currentAlerts)
  
        replaceAlerts,newAlerts,updateAlerts = omCommon.checkAlerts(currentAlerts['results'], iDeployConfig['alerts'])
  
        if replaceAlerts:
          if newAlerts:
            for alert in newAlerts:
              result = omCommon.post(baseurl = iDeployConfig['omBaseUrl'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/alertConfigs',
                publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'], data = alert)
              print(result)
              logging.debug(result)
          if updateAlerts:
            for alert in updateAlerts:
              result = omCommon.put(baseurl = iDeployConfig['omBaseUrl'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/alertConfigs/' + alert['id'],
                publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'], data = alert)
              print(result)
              logging.debug(result)

    # Create the process
    logging.debug("Creating Process object...")
    processMemberConfig = omCommon.createProcessMember(fqdn = iDeployConfig['fqdn'], subDomain = iDeployConfig['subDomain'], port = iDeployConfig['port'],
      mongoDBVersion = iDeployConfig['mongoDBVersion'], horizons = {'OUTSIDE': iDeployConfig['horizon']}, replicaSetName = iDeployConfig['replicaSetName'], 
      shardedClusterName = iDeployConfig['shardedClusterName'], deploymentType = iDeployConfig['deploymentType'], cert_path = iDeployConfig['cert_path'])
    logging.debug(processMemberConfig)

    # Create the replica set member
    logging.debug("Creating Replica Set object...")
    rsMemberConfig = omCommon.createReplicaSetMember(replicaSetName = iDeployConfig['replicaSetName'], priority = iDeployConfig['priority'],
      arbiter = iDeployConfig['arbiter'], horizons = {'OUTSIDE': iDeployConfig['horizon']})
    logging.debug(rsMemberConfig)

    # get the current configuration
    logging.debug("Get current config...")
    currentConfig = omCommon.get(baseurl = iDeployConfig['omBaseUrl'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig',
      publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])

    # add the automation agent section if missing
    logging.debug("Creating Automation Agent object...")
    addAA,currentConfig = omCommon.add_missing_aa(currentConfig = currentConfig, opsManagerAddress = iDeployConfig['omBaseUrl'])

    # remove keys that are not required
    currentConfig.pop('mongoDbVersions')
    currentConfig.pop('version')
    logging.debug("\033[91mCurrent config:\033[0;0m %s" % currentConfig)

    # get the full config payload
    # determine if the member is already in the deployment
    logging.debug("Creating proper process object...")
    replaceP,currentConfig['processes'],currentHost = omCommon.checkProcesses(currentProcess = currentConfig['processes'], newProcess = processMemberConfig,
      replicaSetName = iDeployConfig['replicaSetName'])
    logging.debug("Post Processes: %s" % currentConfig['processes'])

    if iDeployConfig['deploymentType'] != 'ms':
      replaceRS,currentConfig['replicaSets'] = omCommon.checkReplicaSet(currentReplicaSets = currentConfig['replicaSets'], replicaSetName = iDeployConfig['replicaSetName'],
      memberName = currentHost, memberConfig = rsMemberConfig)
      logging.debug("Post RS: %s" % currentConfig['replicaSets'])

      if iDeployConfig['shardedClusterName']:
        replaceSH,currentConfig['sharding'] = omCommon.checkShard(currentConfig = currentConfig['sharding'], replicaSetName = currentConfig['replicaSets'],
          shardedClusterName = iDeployConfig['shardedClusterName'], configServer =iDeployConfig['configServerReplicaSet'])
        logging.debug("Post sharding: %s" % currentConfig['sharding'])
      else:
        replaceSH = False
    else:
      replaceRS = False
      replaceSH = False

    replaceBU,currentConfig['backupVersions'] = omCommon.checkBackups(currentBackup = currentConfig['backupVersions'], fqdn = iDeployConfig['fqdn'], backup = iDeployConfig['backup'])
    logging.debug("Post backup agent: %s" % currentConfig['backupVersions'])

    replaceMon,currentConfig['monitoringVersions'] = omCommon.checkMonitoring(currentMonitoring = currentConfig['monitoringVersions'], fqdn = iDeployConfig['fqdn'],
      monitoring = iDeployConfig['monitoring'])
    logging.debug("Post Monitoring agent: %s" % currentConfig['monitoringVersions'])

    if any([addAA, replaceP, replaceRS, replaceSH, replaceBU, replaceMon]):

      checkCount = 0
      print("Replacing config...")

      # take a copy of the config
      f = open(('/data/db/' + iDeployConfig['hostname'] + '-' + datetime.now().strftime("%Y%m%d%H%M%S") + ".json"), 'w')
      f.write(json.dumps(currentConfig, indent=2, sort_keys=True))
      f.close()

      # Send config
      reply = omCommon.put(baseurl = iDeployConfig['omBaseUrl'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig', data = currentConfig,
        publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])
      logging.debug("Reply from Ops Manager: %s" % reply)
      print("Reply from Ops Manager: %s" % reply)

      logging.debug(currentConfig)

      # get status of the plan
      while checkCount < 20:
        achievedPlan = False
        planStatus = omCommon.get(baseurl = iDeployConfig['omBaseUrl'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationStatus', publicKey = iDeployConfig['publicKey'],
        privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])

        for plan in planStatus['processes']:
          logging.debug("CurrentVersion: %s, GoalVersion: %s" % (plan['lastGoalVersionAchieved'], planStatus['goalVersion']))
          if plan['lastGoalVersionAchieved'] != planStatus['goalVersion']:
            if plan['errorCode'] != 0:
              logging.warn("\033[91mWARN!\033[0;0m %s\n%s\n%s" % (plan['errorCodeDescription'],plan['errorCodeHumanReadable'],plan['errorString']))
              print("\033[91mWARN!\033[0;0m %s\n%s\n%s" % (plan['errorCodeDescription'],plan['errorCodeHumanReadable'],plan['errorString']))
            else:
              logging.debug("Applying stage: %s" % plan['plan'])
              print("Applying stage: %s" % plan['plan'])
          else:
            achievedPlan = True
            break
        checkCount += 1
        if achievedPlan is True:
          break
        # sleep and wait to check again
        sleep(15)
      if achievedPlan is False:
        logging.exception("\033[91mERROR!\033[0;0m, the plan has not been applied.")
        print("\033[91mERROR!\033[0;0m, the plan has not been applied.")
    else:
      logging.debug("Current config is correct, not replacing")
      print("Current config is correct, not replacing")
    #except Exception as e:
  #  print(e)

if __name__ == "__main__": main()