#
#
try:
  import yaml
  import logging
  from os import getenv,mkdir
  from os.path import isdir
except ImportError as e:
  print(e)
  exit(1)

def aaConfHlpr():
  aaCfg = [
    'logFile=/var/log/mongodb-mms-automation/automation-agent.log',
    'mmsConfigBackup=/var/lib/mongodb-mms-automation/mms-cluster-config-backup.json',
    'dialTimeoutSeconds=40',
    'logLevel=INFO',
    'maxLogFiles=10',
    'maxLogFileSize=268435456',
    'maxLogFileDurationHrs=24',
    'tlsRequireValidMMSServerCertificates=true'
  ]
  return aaCfg

def getEnvData():
  iConfig = aaConfHlpr()
  try:
    iConfig.extend(('mmsBaseUrl=' + getenv('MMSBASEURL'), 'mmsApiKey=' + getenv('MMSAPIKEY'), 'mmsGroupId=' + getenv('MMSGROUPID')))
    with open('/init/mongod.conf','r') as f:
      i = yaml.safe_load(f)
      iConfig.extend(('httpsCAFile=' + i['net']['tls']['CAFile'], 'tlsMSServerClientCertificate=' + i['net']['tls']['certificateKeyFile']))
      f.close()
    logging.debug(iConfig)
    return iConfig
  except ValueError as e:
    logging.exception("Value Error %s" % e)
    raise Exception('Failure to get environment variables')

def main():
  # Determine logging level
  if getenv('LOGLEVEL').upper() == 'DEBUG':
    logLevel = logging.DEBUG
  else:
    logLevel = logging.INFO
  logging.basicConfig(format='{"ts": "%(asctime)s, "msg": "%(message)s"}', level=logLevel)
  try:
    iCfg = getEnvData()
    logging.debug("DUMP: %s" % iCfg)
    with open('/data/config/automation-agent.config', 'w') as f:
      for cItem in iCfg:
        f.write("{}\n".format(cItem))
      f.close()
  except ValueError as e:
    logging.exception("Value Error %s" % e)
    raise("Value Error %s" % e)

if __name__ == "__main__":
  main()