# Deployer

A Python script to deploy and modify MongoDB replica sets via the Ops Manager API.

Usually run from Kubernetes init container of pods to initially create a replica set if missing and then add the individual pods. This is for situations where the MongoDB Enterprise Kubernetes Operator cannot be used.

**We recommend using the MongoDB Enterprise Kubernetes Operator where possible**

This is targeted at using DNS Split Horizon for cross-datacentre indepedent Kubernetes cluster, where the pod FQDN is converted to a DNS split horizon name, e.g. from `mongodb-0-0.mongodb-0-svc.mongodb.svc.cluster.local` to `mongodb-0-0.test-env`. The replica set will use the DNS Split Horizon names to initiate and configure the replica set and not the full FQDN. This requires DNS split horizon enabled outside of kubernetes and for CoreDNS to be configured to forward non-Kubernetes domain lookups to the DNS server configured with split horizon. The pod also needs the DNS split horizon name (e.g. `test-env`) as a search in its `/etc/resolv.conf`.

# Prerequisites

The following non-standard Python libraries are required:

* omCommon (part of this repository)
* requests (https://pypi.org/project/requests/)

# Usage

Run from within the init container of the popd of interest. The MongoDB Ops Manager Automation Agent must be installed within the containers.

To run the program use to use the FQDN as reported by the operating system:

```shell
python3 deployer.py
```
Or the following to use a specific FQDN:

```
python3 deployer.py mongod0.mongodb.local
```

# Configuration

An Ops Manager API Access Key is required for the Project or the parent Organisation with at least [Project Automation Admin](https://docs.opsmanager.mongodb.com/current/reference/user-roles/#Project-Automation-Admin) role.

The `config.json` file must exist in the same directory as the `deployer.py` with the following basic structure:

```json
{
  "omBaseURL": "https://mongod0.mongodb.local:8443/api/public/v1.0",
  "projectID": "5f87840518322b1e72ddff8d",
  "publicKey": "PLUMEAAW",
  "privateKey": "0aebb38f-3ae5-4436-9267-7f92318610a3",
  "subDomain": "test-env",
  "dnsSuffix": "mongodb.local",
  "ca_cert_path": "/absolute/path/to/ca/cert",
  "port": 27017,
  "replicaSetName": "rs0",
  "shardedClusterName": "myShardedCluster",
  "mongoDBVersion": "4.4.5-ent",
  "processType": "mongos",
  "shardType": "configserver",
  "configServerReplicaSet": "cs0",
  "priority": {
    "mongod-0-0": 2
  },
  "arbiter": [
    "mongod-0-2"
  ],
  "nonBackupAgent": [
    "mongod-0-2"
  ],
  "nonMonitoringAgent": []
}
```

### omBaseURL

The URL of the Ops Manager, including the protocol and the base of the path, e.g. `https://mongod0.mongodb.local:8443/api/public/v1.0`

### projectID

The project identifier for the Ops Manager Project.

### publicKey

The public key componenet of the Ops Manager Project API Access Key, see [MongoDB documentation](https://docs.opsmanager.mongodb.com/current/tutorial/manage-programmatic-api-keys/)

### privateKey

The private key componenet of the Ops Manager Project API Access Key, see [MongoDB documentation](https://docs.opsmanager.mongodb.com/current/tutorial/manage-programmatic-api-keys/)

### ca_cert_path

Absolute path to the CA certificate for Ops Manager.

## subDomain

The partial domain name used for the DNS split horizon, e.g. `test-env` to make `mongodb-0-0.test-env` from `mongodb-0-0.mongodb-0-svc.mongodb.svc.cluster.local`. This is for cross-cluster communications and required DNS split horizon enabled outside of kubernetes and for CoreDNS to be configured to forward non-Kubernetes domains to the DNS server configured with split horizon.

### dnsSuffix

The DNS domain used to create the hostname that allows communication with the individual MongoDB instance from outside Kubernetes via MongoDB Split Horizon, e.g. `mongodb.local` to give `mongodb-0-0.test-env.mongodb.local`.

### port

Port number required for the MongoDB deployment.

### replicaSetName

Name of the MongoDB replica set/shard, required for replica sets and sharded clusters, this includes the config server replica set for sharded clusters.

### shardedClusterName

Name of the sharded cluster, only required for sharded clusters.

### mongoDBVersion

Version of MongoDB to use in the deployment. Append `-ent` for Enterprise, e.g. `4.4.4-ent`.

### shardType - REQUIRED FOR SHARDING IF CONFIG SERVER

If a sharded cluster this must be include for config servers, set to `configserver`.

### processType - REQUIRED FOR SHARDING IF MONGOS

Defaults to `mongod`. If a mongos is required include this attribute with `mongos` as the value.

### configServerReplicaSet - REQUIRED FOR SHARDING IF MONGOD

Name of the config server replica set.

### priority - OPTIONAL

An object of short hostname and priorities for any MongoDB instance that requires a priority greater than 1. Arbiters are automatically set to 0.

### arbiter - OPTIONAL

An array of short hostnames of MongoDB instances that should be filthy aribters.

### nonBackupAgent - OPTIONAL

An array of short hostnames of MongoDB instances that shout NOT have the backup agent enabled on the pod.

### nonMonitoringAgent - OPTIONAL

An array of short hostnames of MongoDB instances that shout NOT have the monitoring agent enabled on the pod.