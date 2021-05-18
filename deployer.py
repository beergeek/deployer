try:
  from datetime import datetime
  import json
  import omCommon
  import os
  import re
  import socket
  import sys
except ImportError as e:
  print(e)
  exit(1)

# Check the configuration for validity
def configChecker(iConfig, args):
  # check if FQDN provided, if not use hostname from os
  if len(args) > 1:
    allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    iConfig['fqdn'] = sys.argv[1]
    if iConfig['fqdn'][-1] == ".":
      iConfig['fqdn'] = fqdn[:-1] # strip exactly one dot from the right, if present
    if all(allowed.match(x) for x in iConfig['fqdn'].split(".")) == False:
      print("%s is not a valid FQDN" % iConfig['fqdn'])
      raise Exception("%s is not a valid FQDN" % iConfig['fqdn'])
  else:
    iConfig['fqdn'] = socket.gethostname()
  iConfig['hostname'] = iConfig['fqdn'].split('.')[0]
  iConfig['splitName'] = iConfig['hostname'] + '.' + iConfig['subDomain']
  iConfig['outsideName'] = iConfig['splitName'] + '.' + iConfig['dnsSuffix'] + ':' + str(iConfig['port'])
  if 'ca_cert_path' not in iConfig:
    raise Exception("The `ca_cert_path` must exist in the config file")
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

  return iConfig

def main():
  #try:
    if os.path.isfile(sys.path[0] + '/config.json') == False:
      print("\033[91mERROR! The `config.json` file must be in the ame directory as `deployer.py`\033[m")
      raise Exception("\033[91mERROR! The `config.json` file must be in the ame directory as `deployer.py`\033[m")

    with open(sys.path[0] + '/config.json', 'r') as f:
      iDeployConfig = json.load(f)

    # check input
    iDeployConfig = configChecker(iConfig = iDeployConfig, args = sys.argv)

    # Create the process
    processMemberConfig = omCommon.createProcessMember(fqdn = iDeployConfig['fqdn'], subDomain = iDeployConfig['subDomain'], port = iDeployConfig['port'], mongoDBVersion = iDeployConfig['mongoDBVersion'], horizons = {'OUTSIDE': iDeployConfig['outsideName']}, replicaSetName = iDeployConfig['replicaSetName'], 
    shardedClusterName = iDeployConfig['shardedClusterName'], deploymentType = iDeployConfig['deploymentType'])

    # Create the replica set member
    rsMemberConfig = omCommon.createReplicaSetMember(replicaSetName = iDeployConfig['replicaSetName'], priority = iDeployConfig['priority'], arbiter = iDeployConfig['arbiter'], horizons = {'OUTSIDE': iDeployConfig['outsideName']})

    # get teh current configuration
    currentConfig = omCommon.get(baseurl = iDeployConfig['omBaseURL'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig', publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])

    # add the automation agent section if missing
    currentConfig = omCommon.add_missing_aa(currentConfig = currentConfig, opsManagerAddress = iDeployConfig['omBaseURL'])

    # remove keys that are not required
    currentConfig.pop('mongoDbVersions')
    currentConfig.pop('version')

    # get the full config payload
    requiredConfig = omCommon.findAndReplaceMember(fqdn = iDeployConfig['fqdn'], replicaSetName = iDeployConfig['replicaSetName'], currentConfig = currentConfig, rsMemberConfig = rsMemberConfig, processMemberConfig = processMemberConfig, monitoring = iDeployConfig['monitoring'], backup = iDeployConfig['backup'], 
      shardedClusterName = iDeployConfig['shardedClusterName'], configServer = iDeployConfig['configServerReplicaSet'], deploymentType = iDeployConfig['deploymentType'])
    f = open((iDeployConfig['hostname'] + '-' + datetime.now().strftime("%Y%m%d%H%M%S") + ".json"), 'w')
    f.write(json.dumps(requiredConfig, indent=2, sort_keys=True))
    f.close()

    # Send config
    reply = omCommon.put(baseurl = iDeployConfig['omBaseURL'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig', data = requiredConfig, publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])
    print("Reply from Ops Manager: %s" % reply)
  #except Exception as e:
  #  print(e)

if __name__ == "__main__": main()