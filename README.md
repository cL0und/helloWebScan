# helloWebScan

## Description
Web scanner based on Python 3.6 aiohttp

## Install
pip3 install aiohttp cchardet bs4 lxml

## Use
Now helloWebScan supports scanning in CIDR format and scanning in underlying masscan JSON result format.

example CIDR:
```bash
python3 helloWebScan.py -r 192.168.99.0/24,192.168.98.0/24 -p 80,8080,8081
```

example json file:
```bash
python3 helloWebScan.py -f masscan.json
```

You can also specify maximum concurrent connections by -q:
```bash
python3 helloWebScan.py  -r 192.168.99.0/24 -p80 -q 10000
```

good luck :)
