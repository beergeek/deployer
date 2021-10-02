#!/usr/bin/env python3
# /
  # @GIT$Format:[%h] %ci %cn - %s$
  #
  # Python script to perform download, uncompress, and start the automation agent
  # Allows the automation agent to be restarted during updates without the pods crashing.
  #
  # Author: Brett Gray
  #
  # Usage:
  #   path/to/startAgent.py
# /
try:
  import logging
  import agentCommon
  import os
  import platform
  import signal
  import subprocess
  import time
except ImportError as e:
  print(e)
  exit(1)

# set the configuration file
iCfg = {}

# /
  # Description: function to gracefully kill the automation agent and mongod process on SIGTERM/SIGINT
  #
  # Use the items from the configuration file to find the location automation agent application PID and mongod PID
  #
# /
def killAll(signum, frame):
  if os.path.exists(iCfg['aaPidPath']):
    aaPidFile = open(iCfg['aaPidPath'], 'r')
    aaPid = aaPidFile.readline().strip()
    aaPidFile.close()

    if aaPid:
      try:
        os.kill(int(aaPid), signal.SIGTERM)
      except ValueError:
        logging.warn("Cannot stop Automation Agent gracefully")
        print("Cannot stop Automation Agent gracefully")

  if os.path.exists(iCfg['mongoPidPath']):
    mdbPidFile = open(iCfg['mongoPidPath'], 'r')
    mdbPid = mdbPidFile.readline().strip()
    mdbPidFile.close()

    if mdbPid:
      try:
        os.kill(int(mdbPid), signal.SIGTERM)
      except ValueError:
        logging.warn("Cannot stop MongoD gracefully")
        print("Cannot stop MongoD gracefully")


signal.signal(signal.SIGTERM, killAll)
signal.signal(signal.SIGINT, killAll)


def main():
  try:

    # get configuration, or set defaults
    iCfg['configPath']    = os.getenv('AACONFIG', default="/data/config/automation-agent.config")
    iCfg['aaPidPath']     = os.getenv('AAPID', default="/var/run/mongodb-mms-automation/mongodb-mms-automation-agent.pid")
    iCfg['mongoPidPath']  = os.getenv('MDBPID', default="/data/db/mongod.lock")
    iCfg['logLevel']      = os.getenv('LOGLEVEL', default='INFO')
    iCfg['aaPath']        = os.getenv('AAPATH', default="/data/config/bin/mongodb-mms-automation-agent")

    # Determine logging level
    if iCfg['logLevel'].upper() == 'DEBUG':
      logLevel = logging.DEBUG
    else:
      logLevel = logging.INFO
    logging.basicConfig(format='{"ts": "%(asctime)s, "msg": "%(message)s"}', level=logLevel)

    onDisk = agentCommon.checkAA()

    if os.path.exists(iCfg['aaPath']) is False:
      logging.error("Automation agent not on disk! Failing....")
      raise Exception("Automation agent not on disk! Failing....")

    logging.debug("Starting automation agent...")  
    pProc = subprocess.Popen([iCfg['aaPath'], "-f", iCfg['configPath'], '--pidfilepath', iCfg['aaPidPath']], stdin = None, stdout = subprocess.PIPE, stderr = subprocess.PIPE, start_new_session=True)

    logging.debug("Starting sleep so automation can run and restart without killing pod....yawn")
    while 1:
      time.sleep(10)

    logging.debug("Exiting nicely....goodbye")

  except Exception as e:
    logging.error(e)
    raise Exception(e)

if __name__ == "__main__":
  main()
