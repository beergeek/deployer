# /
  # Description: Script to determine if replica set is initialise, initialise if not, check and add member if missing
  #
  # fucntions:
  #   main: basic entry point
  #   newMember: basic object for a new replica set member
  #   executeMongoDBAdmin: fucntion to create MongoDB client connection and execute admin commands
  #   getAddress:  Attempts to resolve addresses
# /

try:
  import socket
  import json
  import logging
  import os.path
  import os
  import sys
  import time
  import pymongo
  from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure, OperationFailure
  from urllib.parse import quote_plus
except ImportError as e:
  print(e)
  sys.exit(1)

# /
  # Description: function that provides the object for a new replica set member.
  #
  # Inputs:
  #   id: The id of the member
  #   port: The port number for member
  #   hostname: The FQDN of the member
  #   arbiter:  Boolean to determine if member is an arbiter. Defaults to false
  #   priority: The priority of member. Default is 1. For arbiter this is forced to 0.
  #   votes: Number of votes for the member. Default is 1.
  #   horizon: Object describing the horizon host and port. Optional.
# /
def newMember(id, port, hostname, arbiter = False, priority = 1, votes = 1, horizon = None):
  # set priority to 0 if filthy arbiter
  if arbiter == True:
    priority = 0
  
  newMemberConfig = {
    "_id" : id,
    "host" : hostname + ":" + str(port),
    "arbiterOnly" : arbiter,
    "buildIndexes" : True,
    "hidden" : False,
    "priority" : priority,
    "tags" : {
    },
    "slaveDelay" : 0,
    "votes" : votes
  }

  if horizon != None:
    newMemberConfig['horizons'] = { 'EXTERNAL': horizon }

  return newMemberConfig

# /
  # Description: function to create MongoDB client and execute admin commands.
  #
  # Inputs:
  #   connectionString: The MongoDB connection string for the host or replica set
  #   caFile: The absolute path for the CA file
  #   command: MongoDB admin command to execute
  #   tls:  Boolean to determine if TLS is used, which it should be!
  #   invalidHost: Boolean to describe of checking hostname for TLS is skipped. Default is False. Should only be true to initialise replica set
# /
def executeMongoDBAdmin(connectionString, caFile, command, tls = True, invalidHost = False):
  try:
    logging.debug("Connection string: %s" % connectionString)
    if tls == True:
      client = pymongo.MongoClient(connectionString, serverSelectionTimeoutMS=5000, ssl=True, ssl_ca_certs=caFile, tlsAllowInvalidHostnames=invalidHost)
    else:
      client = pymongo.MongoClient(connectionString, serverSelectionTimeoutMS=5000, ssl=False)

    output = client.admin.command(command)

    client.close()
    return output
  except (ServerSelectionTimeoutError, ConnectionFailure) as e:
    logging.exception("\033[91mERROR!\033[m %s" % e)
    sys.exit(1)

# /
  # Description: function to attempt to resolve hostnames to address.
  #
  # Inputs:
  #   address: The FQDN to attempt to resolve to an IP
# /
def getAddress(address):
  delay = 10
  count = 0
  while True:
    try:
      logging.debug("Attempting to resolve %s" % address)
      ip = socket.gethostbyname(address)
      return True
    except:
      count += 1
      if count > 15:
        return False
      logging.debug("Could not resolve %s, sleeping...." % address)
      time.sleep(delay)




def main():
  # Basic configuration data from the environment variables
  config = {
    "rootUsername": os.getenv('ADMINUSER'),
    "rootPasswd": os.getenv('ADMINPASSWD'),
    "setName": os.getenv('REPLICASET'),
    "caFile": "/data/ca/ca.pem",
    "port": os.getenv('PORT'),
    "logLevel": os.getenv('LOGLEVEL', default='INFO'),
    "horizon": None
  }

  # Determine logging level
  if config['logLevel'].upper() == 'DEBUG':
    logLevel = logging.DEBUG
  else:
    logLevel = logging.INFO
  logging.basicConfig(format='{"ts": "%(asctime)s, "msg": "%(message)s"}', level=logLevel)

  # Check variables
  if not all(position in config for position in ['port','setName','caFile','rootUsername','rootPasswd']):
    logging.exception("The environment variables requires `PORT`, `REPLICASET`, `LOGLEVEL`, `ADMINUSER`, and `ADMINPASSWD` attributes")

  # determine if CA file exists, if so assume we are using TLS (as we should always use!)
  if os.path.isfile(config['caFile']):
    config['tls'] = True
    logging.info('CA Certificate File does exist, use TLS')
  else:
    config['tls'] = False
    logging.info("\033[95mWARNING!\033[m CA Certificate File does not exist, not using TLS!!!!")

  # Get the hostname and assume the primary is the `0` member of the cluster based on current hostname
  hostname = socket.getfqdn()
  hostSplit = hostname.split('.')
  hostBase =  hostSplit[0].split('-')
  hostNumber = int(hostBase[-1])
  hostBase[-1] = '0'
  hostSplit[0] = '-'.join(hostBase)
  guessedPrimary = '.'.join(hostSplit)

  # Determine if we are requiring access from external to k8s, add Horizon and Service is we do.
  if os.getenv('HORIZONADDR') and os.getenv('HORIZONPORT') is not None:
    config['horizon'] = os.getenv('HORIZONADDR') + ':' + str(int(os.getenv('HORIZONPORT')) + hostNumber)

  logging.debug("Config parameters: %s" % config)
  
  # Check if the "guessed" primary can be resolved (indicates service issue in k8s normally if it cannot be resolved)
  logging.debug("Using %s as guessed primary." % guessedPrimary)
  foundHost = getAddress(guessedPrimary)
  if foundHost == False:
    logging.exception("\033[91mERROR!\033[m Failed to resolve address: %s" % guessedPrimary)
    sys.exit(1)

  connectionString = 'mongodb://' + guessedPrimary + ":" + str(config['port'])

  # get primary, hopefully
  mongoDBData = executeMongoDBAdmin(connectionString = connectionString, caFile = config['caFile'], command = 'ismaster', tls = config['tls'])
  logging.debug(mongoDBData)

  # Determine if replica set exists.
  # Initialise if it is not. Check if host is already a member of replkica set exists.
  if 'setName' in mongoDBData:
    try:
      # determine if host is already a member fo the replica set
      # skip if already a member, add if not.
      if 'hosts' in mongoDBData and (hostname + ':' + str(config['port'])) in mongoDBData['hosts']:
        logging.info("Host already in configuration, skipping...")
        output = mongoDBData
        logging.debug("Current Configuration with host: %s" % mongoDBData)
      else:
        logging.info("Adding new member...")
        # correct connection string for replica set
        realPrimary = "mongodb://" + quote_plus(config['rootUsername']) + ":" + quote_plus(config['rootPasswd']) + "@" + mongoDBData['primary'] + '/?replicaSet=' + mongoDBData['setName']
        currentConfig = executeMongoDBAdmin(connectionString = realPrimary, caFile = config['caFile'], command = {"replSetGetConfig": 1}, tls = config['tls'])
        logging.debug("Current Configuration: %s" % currentConfig)
        currentConfig['config']['members'].sort(key=lambda x: x.get('_id'))
        new = newMember(id=(currentConfig['config']['members'][-1]['_id'] + 1), port = config['port'], hostname = hostname, horizon = config['horizon'])
        newConfig = currentConfig['config']
        newConfig['members'].append(new)
        newConfig['version'] = int(newConfig['version']) + 1
        output = executeMongoDBAdmin(connectionString = realPrimary, caFile = config['caFile'], command = {'replSetReconfig': newConfig}, tls = config['tls'])
        logging.debug("Post adding member return: %s" % output)
    except (ServerSelectionTimeoutError, ConnectionFailure, OperationFailure) as e:
      logging.exception("\033[91mERROR!\033[m %s" % e)
      sys.exit(1)
  else:
    try:
      # connect to local host and initialise replica set
      logging.info("No replica set, initialising replica set...")
      output = executeMongoDBAdmin(connectionString = "mongodb://localhost:" + str(config['port']) , caFile = config['caFile'], command = { "replSetInitiate" : {"_id": config['setName'], "members": [{"_id": 0, "host": hostname + ":" + str(config['port']) }]}}, tls = config['tls'], invalidHost = True)
      logging.debug("Post initialisation return: %s" % output)
      logging.info("Adding first user...")
      user = executeMongoDBAdmin(connectionString = "mongodb://localhost:" + str(config['port']) , caFile = config['caFile'], command = {"createUser": config['rootUsername'], "pwd": config['rootPasswd'], "roles": [ "root" ]}, tls = config['tls'], invalidHost = True)
      logging.debug("Created first user return value: %s" % user)
    except (ServerSelectionTimeoutError, ConnectionFailure, OperationFailure) as e:
      logging.exception("\033[91mERROR!\033[m %s" % e)
      sys.exit(1)

    # add horizon if required
    if config['horizon'] is not None:
      delay = 10
      count = 0
      while True:
        count += 1
        try:
          logging.info("Adding horizon for primary...")
          currentConfig = executeMongoDBAdmin(connectionString = "mongodb://" + quote_plus(config['rootUsername']) + ":" + quote_plus(config['rootPasswd']) + "@" + hostname + ":" + str(config['port']) , caFile = config['caFile'], command = {"replSetGetConfig": 1}, tls = config['tls'])
          logging.debug("Current Configuration after initialisation: %s" % currentConfig)
          newConfig = currentConfig['config']
          newConfig['version'] = int(newConfig['version']) + 1
          newConfig.pop('term')
          newConfig['members'][0]['horizons'] = { 'EXTERNAL': config['horizon'] }
          logging.debug("New Configuration: %s" % newConfig)
          output = executeMongoDBAdmin(connectionString = "mongodb://" + quote_plus(config['rootUsername']) + ":" + quote_plus(config['rootPasswd']) + "@" + hostname + ":" + str(config['port']) , caFile = config['caFile'], command = {'replSetReconfig': newConfig}, tls = config['tls'])
          logging.debug("Post horizon return value: %s" % output)
          break
        except OperationFailure as e:
          if count > 5:
            logging.exception("\033[91mERROR!\033[mFailed to apply horizon fives times, aborting")
            sys.exit(1)
          logging.info("Failed to add horizon, this is attempt %s. Trying again..." % str(count))
          time.sleep(delay)

  sys.exit(0)

if __name__ == "__main__":
  main()