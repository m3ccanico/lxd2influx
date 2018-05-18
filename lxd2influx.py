#!/usr/bin/env python3


INFLUX_DB_PORT = 8086
INFLUX_DB_IP = '172.31.40.72'
INFLUX_DB_NAME = 'lxd'

CGROUP_PREFIX = '/sys/fs/cgroup'

STATUS_RUNNING = 103
STATUS_SUCCESS = 200

INTERVAL = 10

import os
import re
import time
import platform
import subprocess

import pprint
pp = pprint.PrettyPrinter(indent=2)

#from pylxd import Client
from influxdb import InfluxDBClient
from datetime import datetime
from pytz import timezone
from nsenter import Namespace

import requests
import requests_unixsocket
requests_unixsocket.monkeypatch()

localtz = timezone('Pacific/Auckland')


def main():
    
    hostname = platform.node()
    
    # connect to DB
    influx = InfluxDBClient(INFLUX_DB_IP, INFLUX_DB_PORT, '', '', INFLUX_DB_NAME)
    server(hostname, influx)


def server(hostname, influx):
    
    done = 0
    
    while True:
        ts = round(time.time())
        if ts % INTERVAL == 0 and ts != done:
            done = ts
            update_meassurement(hostname, influx, ts)
        time.sleep(0.5)


def update_meassurement(hostname, influx, ts):
    ts = datetime.fromtimestamp(ts, localtz)
    ts_formated = ts.strftime('%Y-%m-%dT%H:%M:%S%Z')
    
    r = requests.get('http+unix://%2Fvar%2Flib%2Flxd%2Funix.socket/1.0/containers')
    if r.status_code == STATUS_SUCCESS:
        json = r.json()
    else:
        return
    
    measurements = []
    
    for container in json['metadata']:
        container_name = container.split('/')[-1]
        
        r = requests.get('http+unix://%2Fvar%2Flib%2Flxd%2Funix.socket/1.0/containers/{}/state'.format(container_name))
        if r.status_code == STATUS_SUCCESS:
            json = r.json()
            #pp.pprint(json)
            
            if int(json['metadata']['status_code']) == STATUS_RUNNING:
                
                # CPU
                # /sys/fs/cgroup/cpu/lxc/*/cpuacct.stat
                with open(os.path.join(CGROUP_PREFIX, 'cpu', 'lxc', container_name, 'cpuacct.stat'), 'r') as cgroup:
                    lines = cgroup.read().splitlines()
                    
                    cpu_user = 0
                    cpu_system = 0
                    
                    for line in lines:
                        data = line.split()
                        if data[0] == "user":
                            cpu_user = int(data[1])
                        elif data[0] == "system":
                            cpu_system = int(data[1])
                    
                    # create CPU meassurement
                    measurement = {
                        "measurement": "cpu",
                        "tags": {
                            "host":      hostname,
                            "container": container_name,
                        },
                        "time": ts_formated,
                        "fields": {
                            "cpuacct.stat.user": cpu_user,
                            "cpuacct.stat.system": cpu_system,
                        }
                    }
                    measurements.append(measurement)
                    #pp.pprint(measurement)
                
                # Memory
                usage_in_bytes = int(json['metadata']['memory']['usage'])
                
                # create memory meassurement
                measurement = {
                    "measurement": "memory",
                    "tags": {
                        "host":      hostname,
                        "container": container_name,
                    },
                    "time": ts_formated,
                    "fields": {
                        "memory.usage_in_bytes": usage_in_bytes,
                    }
                }
                measurements.append(measurement)
                #pp.pprint(measurement)
                
                for interface in json['metadata']['network']:
                    # only include eth interfaces
                    if re.match('^eth', interface):
                        # create network meassurement
                        measurement = {
                            "measurement": "network",
                            "tags": {
                                "host":      hostname,
                                "container": container_name,
                                "interface": interface,
                            },
                            "time": ts_formated,
                            "fields": {
                                "rx_bytes":   int(json['metadata']['network'][interface]['counters']['bytes_received']),
                                "tx_bytes":   int(json['metadata']['network'][interface]['counters']['bytes_sent']),
                                "rx_packets": int(json['metadata']['network'][interface]['counters']['packets_received']),
                                "tx_packets": int(json['metadata']['network'][interface]['counters']['packets_sent']),
                            }
                        }
                        measurements.append(measurement)
    
    #pp.pprint(measurements)
    influx.write_points(measurements)


if __name__ == "__main__":
    main()