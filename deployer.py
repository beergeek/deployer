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

def main():
  try:
    if os.path.isfile(sys.path[0] + '/config.json') == False:
      print("\033[91mERROR! The `config.json` file must be in the ame directory as `deployer.py`\033[m")
      raise Exception("\033[91mERROR! The `config.json` file must be in the ame directory as `deployer.py`\033[m")

    with open(sys.path[0] + '/config.json', 'r') as f:
      iDeployConfig = json.load(f)

    # check if FQDN provided, if not use hostname from os
    if len(sys.argv) > 1:
      allowed = re.compile("(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
      fqdn = sys.argv[1]
      if fqdn[-1] == ".":
        fqdn = fqdn[:-1] # strip exactly one dot from the right, if present
      if all(allowed.match(x) for x in fqdn.split(".")) == False:
        print("%s is not a valid FQDN" % fqdn)
        raise Exception("%s is not a valid FQDN" % fqdn)
    else:
      fqdn = socket.gethostname()
    hostname = fqdn.split('.')[0]
    splitName = hostname + '.' + iDeployConfig['subDomain']
    outsideName = splitName + '.' + iDeployConfig['dnsSuffix'] + ':' + str(iDeployConfig['port'])

    if 'ca_cert_path' not in iDeployConfig:
      raise Exception("The `ca_cert_path` must exist in the config file")

    if 'priority' in iDeployConfig and hostname in iDeployConfig['priority']:
      priority = iDeployConfig['priority'][hostname]
    else:
      priority = 1

    if 'arbiter' in iDeployConfig and hostname in iDeployConfig['arbiter']:
      arbiter = True
    else:
      arbiter = False

    if 'nonBackupAgent' in iDeployConfig and hostname in iDeployConfig['nonBackupAgent']:
      backup = False
    else:
      backup = True

    if 'nonMonitoringAgent' in iDeployConfig and hostname in iDeployConfig['nonMonitoringAgent']:
      monitoring = False
    else:
      monitoring = True

    processMemberConfig = omCommon.createProcessMember(fqdn = fqdn, subDomain = iDeployConfig['subDomain'], port = iDeployConfig['port'], mongoDBVersion = iDeployConfig['mongoDBVersion'], horizons = {'OUTSIDE': outsideName}, replicaSetName = iDeployConfig['replicaSetName'],)
    rsMemberConfig = omCommon.createReplicaSetMember(replicaSetName = iDeployConfig['replicaSetName'], priority = priority, arbiter = arbiter, horizons = {'OUTSIDE': outsideName})

    # get teh current configuration
    currentConfig = omCommon.get(baseurl = iDeployConfig['omBaseURL'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig', publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])

    # remove keys that are not required
    currentConfig.pop('mongoDbVersions')
    currentConfig.pop('version')

    # get the full config payload
    requiredConfig = omCommon.findAndReplaceMember(fqdn = fqdn, replicaSetName = iDeployConfig['replicaSetName'], currentConfig = currentConfig, rsMemberConfig = rsMemberConfig, processMemberConfig = processMemberConfig, monitoring = monitoring, backup = backup)
    f = open((hostname + '-' + datetime.now().strftime("%Y%m%d%H%M%S") + ".json"), 'w')
    f.write(json.dumps(requiredConfig, indent=2, sort_keys=True))
    f.close()

    # Send config
    reply = omCommon.put(baseurl = iDeployConfig['omBaseURL'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig', data = requiredConfig, publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = iDeployConfig['ca_cert_path'])
    print("Reply from Ops Manager: %s" % reply)
  except Exception as e:
    print(e)

if __name__ == "__main__": main()