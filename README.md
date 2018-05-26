# lxd2influx

Reads performance data from local LXD (CPU jiffies, memory usage, bytes sent/received) and writes them to InfluxDB.

## Install libraries

With PIP:
```bash
pip3 install influxdb requests requests_unixsocket
```
or
```bash
pip3 install -r requirements.txt
```

## Install script as a service

```bash
cp lxd2influx.py /usr/local/sbin/
cp lxd2influx.service /lib/systemd/system/
systemctl daemon-reload
systemctl enable lxd2influx.service
```

Check status of service

```bash
systemctl status lxd2influx.service
```

## Run

In case you would like to run the script manually and not as a service. 

The script needs to run as root to access the different container namespaces.

```bash
nohup ./lxd2influx.py &
```

## Todo

* Put settings into configuration file
* Move hardcoded path to socket into configuration file
