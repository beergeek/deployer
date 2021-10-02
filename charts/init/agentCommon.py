try:
  import glob
  import logging
  import os
  import requests
  import subprocess
  import tarfile
except ImportError as e:
  print(e)
  exit(1)

TMPPATH   = "/var/tmp/"
MMSPATH   = "/download/agent/automation/"
MMSAANAME = "mongodb-mms-automation-agent-latest."
AAEXT     = ".tar.gz"
AADIR     = "/data/config"
AABINDIR  = AADIR + "/bin"
AAPROG    = AABINDIR + "/mongodb-mms-automation-agent"

# /
  # Description: function to download the automation agent tarball from Ops Manager
  #
  # Use the items from the configuration file to set the address for Ops manager and the automation agent tarball name
  #
# /
def downloadAA(iCfg):
  try:
    logging.debug("Downloading automation agent tarball from %s" % iCfg['mmsBaseUrl'])
    url = iCfg['mmsBaseUrl'] + MMSPATH + MMSAANAME + iCfg['os'] + "_" + iCfg['arch'] + AAEXT
    if os.path.exists(iCfg['caFile']):
      data = requests.get(url, allow_redirects=True, verify=iCfg['caFile'])
    else:
      data = requests.get(url, allow_redirects=True)

    open(TMPPATH + MMSAANAME + iCfg['os'] + "_" + iCfg['arch'] + AAEXT, 'wb').write(data.content)
  except Exception as e:
    logging.error("Failed to download automation agent: %s" % str(e))
    raise Exception("Failed to download automation agent: %s" % str(e))

# /
  # Description: function to uncompressed the automation agent tarball into the desired location
  #
  # Use the items from the configuration file to set the location automation agent application
  #
# /
def uncompressAA(iCfg):
  try:
    logging.debug("Uncompressing automation agent tarball")
    aaFile = tarfile.open(TMPPATH + MMSAANAME + iCfg['os'] + "_" + iCfg['arch'] + AAEXT, 'r:gz')
    aaFile.extractall(path = AADIR)
    aaFile.close()
    for dir in glob.glob(AADIR + "/mongodb-mms-automation-agent-*"):
      if os.path.isdir(dir):
        os.rename(dir, AADIR + "/bin")
        return 0
  except tarfile.TarError as e:
    logging.error(e)
    raise Exception(e)

# /
  # Description: function to check if automnation agent is already installed
  #
  # Use the items from the configuration file to find the automation agent path
  #
# /
def checkAA():
  if os.path.exists(AAPROG):
    logging.debug("Automation agent already exists on disk")
    return True
  logging.debug("Automation agent does not exists on disk")
  return False

# /
  # Description: function to start the automnation agent
  #
  # Use the items from the configuration file to fine the automation agent path and PID file path
  #
# /
def startAA(iCfg):
  logging.debug("Starting automation agent...")
  pProc = subprocess.Popen([AAPROG, "-f", iCfg['configPath'], '--pidfilepath', iCfg['aaPidPath']], shell=True, stdin = None, stdout = None, stderr = None, start_new_session=True)
  #pOutput, pError = pProc.communicate()
  #logging.debug(pOutput)