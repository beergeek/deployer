#!/usr/bin/env python3
# /
  # @GIT$Format:[%h] %ci %cn - %s$
  #
  # Python script to perform health check for MongoDB to verify status.
  # Any one of the follow is classified as healthy:
  #   - Container up for less than 10 minutes
  #   - Automation agent is running
  #   - mongod or mongos running
  #
  # Author: Brett Gray
  #
  # Usage:
  #   path/to/health.py
# /
try:
  import time
  import os
  import subprocess
except ImportError as e:
  print(e)
  exit(1)

# /
  # Description: Checks if the automation agent is alive.
  #   If not, we assume the automation agent is being upgraded
  #
  # Inputs:
  #   pidfile: Absolute path to the PID file for the automation agent
  #
# /
def check_AA_alive(pidfile):
  pProc = subprocess.Popen(["pgrep", "--exact", "mongodb-mms-automation-agent"], stdin = None, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
  pOutput, pError = pProc.communicate()

  if pProc.returncode != 0 and pProc.returncode != 1:
    raise Exception("Failed to execute `pgrep` for `mongodb-mms-automation-agent`: " + str(pError))
  
  if not pOutput:
    return False
  else:
    return True

# /
  # Description: Checks if the container has been up for less than 10 minutes.
  #
  # Inputs:
  #
# /
def get_container_uptime():
  ct = os.path.getctime('/proc/1/stat')
  if ct > (time.time() - 600):
    return True
  return False

# /
  # Description: Checks if a `mongod` process is running.
  #
  # Inputs:
  #
# /
def get_mongod():
  pProc = subprocess.Popen(["pgrep", "--exact", "mongod"], stdin = None, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
  pOutput, pError = pProc.communicate()

  if pProc.returncode != 0 and pProc.returncode != 1:
    raise Exception("Failed to execute `pgrep` for `mongod`: " + str(pError))
  
  if not pOutput:
    return False
  else:
    return True

# /
  # Description: Checks if a `mongos` process is running.
  #
  # Inputs:
  #
# /
def get_mongos():
  pProc = subprocess.Popen(["pgrep", "--exact", "mongos"], stdin = None, stdout = subprocess.PIPE, stderr = subprocess.PIPE)
  pOutput, pError = pProc.communicate()

  if pProc.returncode != 0 and pProc.returncode != 1:
    raise Exception("Failed to execute `pgrep` for `mongos`: " + str(pError))
  
  if not pOutput:
    return False
  else:
    return True

# /
  # Description: Checks if a `mongod` or `mongos` process is running.
  #
  # Inputs:
  #
# /
def get_mongod_mongos():
  return get_mongod() or get_mongos()

def main():
  if os.getenv("PIDFILE"):
    pidfile = os.getenv("PIDFILE")
  else:
    pidfile = "/var/run/mongodb-mms-automation/mongodb-mms-automation-agent.pid"
  
  x = get_container_uptime() or check_AA_alive(pidfile) or get_mongod_mongos()
  if x == False:
    return 1
  return 0


if __name__ == "__main__":
  main()