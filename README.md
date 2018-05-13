# lxd2influx

Reads performance data from local LXD (CPU, memroy, interface statistic) and writes them into InfluxDB.


## Install libraries

With Packages
```bash
apt install python3-pylxd python3-influxdb
```

With PIP:
```bash
pip3 install influxdb pylxd nsenter
```
or
```bash
pip3 install -r requirements.txt
```

## Install service

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

The script needs to run as root to access the different container namespaces.

```bash
nohup ./lxd2influx.py &
```

## Todo

* Remove dependency on pylxd, just read the folders under `cgroup/lxc` instead.
* Put settings into config file
* Create proper da