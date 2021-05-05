try:
  import json
  import omCommon
  import socket
except ImportError as e:
  print(e)
  exit(1)

def main():
  #try:
    with open('config.json', 'r') as f:
      iDeployConfig = json.load(f)

    fqdn = 'mongod7.mongodb.local' #socket.gethostname()
    hostname = fqdn.split('.')[0]
    splitName = hostname + '.' + iDeployConfig['subDomain']
    outsideName = hostname + '.' + iDeployConfig['dnsSuffix'] + ':' + str(27017)

    if 'priority' in iDeployConfig and hostname in iDeployConfig['priority']:
      priority = iDeployConfig['priority'][hostname]
    else:
      priority = 1

    if 'arbiter' in iDeployConfig and hostname in iDeployConfig['arbiter']:
      arbiter = bool(iDeployConfig['arbiter'][hostname])
    else:
      arbiter = False

    processMemberConfig = omCommon.createProcessMember(fqdn = fqdn, subDomain = iDeployConfig['subDomain'], port = iDeployConfig['port'], mongoDBVersion = iDeployConfig['mongoDBVersion'], horizons = {'OUTSIDE': outsideName}, replicaSetName = iDeployConfig['replicaSetName'],)
    rsMemberConfig = omCommon.createReplicaSetMember(replicaSetName = iDeployConfig['replicaSetName'], priority = priority, arbiter = arbiter, horizons = {'OUTSIDE': outsideName})

    currentConfig = omCommon.get(baseurl = iDeployConfig['omBaseURL'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig', publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = '/Users/brettgray/Documents/Dev/CA/certs/ca.pem')
    currentConfig.pop('mongoDbVersions')
    currentConfig.pop('version')
    requiredConfig = omCommon.findAndReplaceMember(fqdn = fqdn, replicaSetName = iDeployConfig['replicaSetName'], currentConfig = currentConfig, rsMemberConfig = rsMemberConfig, processMemberConfig = processMemberConfig)
    f = open('new.json', 'w')
    f.write(json.dumps(requiredConfig, indent=2, sort_keys=True))
    reply = omCommon.put(baseurl = iDeployConfig['omBaseURL'], endpoint = '/groups/' + iDeployConfig['projectID'] + '/automationConfig', data = requiredConfig, publicKey = iDeployConfig['publicKey'], privateKey = iDeployConfig['privateKey'], ca_cert_path = '/Users/brettgray/Documents/Dev/CA/certs/ca.pem')
    print(reply)
  #except Exception as e:
  #  print(e)

if __name__ == "__main__": main()