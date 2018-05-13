#!/usr/bin/env python3


INFLUX_DB_PORT = 8086
INFLUX_DB_IP = '172.31.40.72'
INFLUX_DB_NAME = 'lxd'

CGROUP_PREFIX = '/sys/fs/cgroup'

INTERVAL = 10

import os
import re
import time
import platform
import subprocess

import pprint
pp = pprint.PrettyPrinter(indent=2)

from pylxd import Client
from influxdb import InfluxDBClient
from datetime import datetime
from pytz import timezone
from nsenter import Namespace


localtz = timezone('Pacific/Auckland')


def main():
    
    hostname = platform.node()
    
    # connect to LXD, assumed local using Unix socket
    lxd = Client()
    
    # connect to DB
    influx = InfluxDBClient(INFLUX_DB_IP, INFLUX_DB_PORT, '', '', INFLUX_DB_NAME)
    server(hostname, lxd, influx)


def server(hostname, lxd, influx):
    
    done = 0
    
    while True:
        ts = round(time.time())
        if ts % INTERVAL == 0 and ts != done:
            done = ts
            update_meassurement(hostname, lxd, influx, ts)
        time.sleep(0.5)


def update_meassurement(hostname, lxd, influx, ts):
    ts = datetime.fromtimestamp(ts, localtz)
    ts_formated = ts.strftime('%Y-%m-%dT%H:%M:%S%Z')
    
    measurements = []
    
    for container in lxd.containers.all():
        
        # ignore containers that are not running
        if container.status != "Running":
            continue
        
        # /sys/fs/cgroup/cpu/lxc/*/cpuacct.stat
        with open(os.path.join(CGROUP_PREFIX, 'cpu', 'lxc', container.name, 'cpuacct.stat'), 'r') as cgroup:
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
                    "container": container.name,
                },
                "time": ts_formated,
                "fields": {
                    "cpuacct.stat.user": cpu_user,
                    "cpuacct.stat.system": cpu_system,
                }
            }
            measurements.append(measurement)
            #pp.pprint(measurement)
        
        # /sys/fs/cgroup/memory/lxc/*/memory.usage_in_bytes
        with open(os.path.join(CGROUP_PREFIX, 'memory', 'lxc', container.name, 'memory.usage_in_bytes'), 'r') as cgroup:
            usage_in_bytes = int(cgroup.read())
            
            # create memory meassurement
            measurement = {
                "measurement": "memory",
                "tags": {
                    "host":      hostname,
                    "container": container.name,
                },
                "time": ts_formated,
                "fields": {
                    "memory.usage_in_bytes": usage_in_bytes,
                }
            }
            measurements.append(measurement)
            #pp.pprint(measurement)
        
        # /sys/fs/cgroup/devices/lxc/CONTAINER-NAME/init.scope/tasks
        with open(os.path.join(CGROUP_PREFIX, 'devices', 'lxc', container.name, 'init.scope', 'tasks'), 'r') as cgroup:
            container_PID = cgroup.readline().rstrip()
            with Namespace(container_PID, 'net'):
                with open('/proc/net/dev', 'r') as proc:
                    lines = proc.read().split("\n")
                    # ignore the first two lines
                    # Inter-|Receive                                                |Transmit
                    # face  |bytes packets errs drop fifo frame compressed multicast|bytes packets errs drop fifo colls carrier compressed
                    for line in lines[2:]:
                        # ignore empty line
                        if line.strip() == "":
                            continue
                        
                        (interface, counters) = line.strip().split(':')
                        
                        # only include eth interfaces
                        if re.match('^eth', interface):
                            counters = counters.split()
                            rx_data = counters[0:7]
                            tx_data = counters[8:15]
                            
                            # create memory meassurement
                            measurement = {
                                "measurement": "network",
                                "tags": {
                                    "host":      hostname,
                                    "container": container.name,
                                    "interface": interface,
                                },
                                "time": ts_formated,
                                "fields": {
                                    "rx_bytes":   int(rx_data[0]),
                                    "tx_bytes":   int(tx_data[0]),
                                    "rx_packets": int(rx_data[1]),
                                    "tx_packets": int(tx_data[1]),
                                    "rx_errors":  int(rx_data[2]),
                                    "tx_errors":  int(tx_data[2]),
                                    "rx_drop":    int(rx_data[3]),
                                    "tx_drop":    int(tx_data[3]),
                                }
                            }
                            measurements.append(measurement)
                            #pp.pprint(measurement)
        
    #pp.pprint(measurements)
    influx.write_points(measurements)


if __name__ == "__main__":
    main()