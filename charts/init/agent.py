#
#
try:
  import agentCommon
  import logging
  import platform
  import yaml
  from os import getenv,mkdir
  from os.path import isdir
  from re import match
except ImportError as e:
  print(e)
  exit(1)

# Set some basic constants
RHEL      = "Red Hat Enterprise Linux Server"
CENTOS    = "CentOS Linux"

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

def getEnvData(mmsBaseUrl):
  iConfig = aaConfHlpr()
  try:

    iConfig.extend(('mmsBaseUrl=' + mmsBaseUrl, 'mmsApiKey=' + getenv('MMSAPIKEY'), 'mmsGroupId=' + getenv('MMSGROUPID')))
    with open('/init/mongod.conf','r') as f:
      i = yaml.safe_load(f)
      iConfig.extend(('httpsCAFile=' + i['net']['tls']['CAFile'], 'tlsMMSServerClientCertificate=' + i['net']['tls']['certificateKeyFile']))
      f.close()
    logging.debug(iConfig)
    return iConfig
  except ValueError as e:
    logging.exception("Value Error %s" % e)
    raise Exception('Failure to get environment variables')

def getAgentInfo():
  iConfig = {}
  # validate Ops Manager URL
  if getenv('MMSBASEURL'):
    iConfig['mmsBaseUrl'] = getenv('MMSBASEURL')
  if iConfig['mmsBaseUrl'] is None:
    logging.error("Environment variable MMSBASEURL missing")
    raise Exception("Environment variable MMSBASEURL missing")
  if not match(r"^https?:\/\/.*$", iConfig['mmsBaseUrl']):
    logging.error("Protocol needs to be included in the Ops Manager URL (MMSBASEURL) environment variable (http or https)")
    raise("Protocol needs to be included in the Ops Manager URL (MMSBASEURL) environment variable (http or https)")
  iConfig['configPath']    = getenv('AACONFIG', default="/data/config/automation-agent.config")
  iConfig['aaPidPath']     = getenv('AAPID', default="/var/run/mongodb-mms-automation/mongodb-mms-automation-agent.pid")
  iConfig['mongoPidPath']  = getenv('MDBPID', default="/data/db/mongod.lock")
  iConfig['caFile']        = getenv('CAPATH', default="/data/ca/ca.pem")
  return iConfig

def main():
  # Determine logging level
  if getenv('LOGLEVEL').upper() == 'DEBUG':
    logLevel = logging.DEBUG
  else:
    logLevel = logging.INFO
  logging.basicConfig(format='{"ts": "%(asctime)s, "func": "%(funcName)s", msg": "%(message)s"}', level=logLevel)

  # Create the automation agent configuration file
  try:
    # get the config for the automation agent
    iCfg = getAgentInfo()
    iCfg['aaConfig'] = getEnvData(iCfg['mmsBaseUrl'])

    # get the config to download and run the automation agent
    logging.debug("DUMP: %s" % iCfg)
    with open(iCfg['configPath'], 'w') as f:
      for cItem in iCfg['aaConfig']:
        f.write("{}\n".format(cItem))
      f.close()

    # Download and start the agent

    # Get the remaining config items we may need to show errors if they fail
    # Get the Ops Manager address, with protocol and port (if required)

    iCfg['arch']          = platform.machine()
    if platform.linux_distribution()[0] == RHEL or platform.linux_distribution()[0] == CENTOS:
      if match(r"^7\..*$", platform.linux_distribution()[1]):
        iCfg['os']        = 'rhel7'
      elif match(r"^8\..*$", platform.linux_distribution()[1]):
        iCfg['os']        = 'rhel8'
      else:
        logging.error("Operating systen version is incorrect: %s" % platform.linux_distribution()[1])
        raise Exception("Operating systen version is incorrect: %s" % platform.linux_distribution()[1])
    else:
      logging.error("Operating systen is incorrect: %s" % platform.linux_distribution()[0])
      raise Exception("Operating systen is incorrect: %s" % platform.linux_distribution()[0])

    logging.debug("Configuration: %s" % iCfg)

    onDisk = agentCommon.checkAA()

    if onDisk is False:
      agentCommon.downloadAA(iCfg)
      agentCommon.uncompressAA(iCfg)

    #agentCommon.startAA(iCfg)

    logging.debug("Finished configuring, downloading, and uncompressing the automation agent....goodbye")

  except ValueError as e:
    logging.exception("Value Error %s" % e)
    raise("Value Error %s" % e)
  except Exception as e:
    logging.error(e)
    raise Exception(e)

if __name__ == "__main__":
  main()