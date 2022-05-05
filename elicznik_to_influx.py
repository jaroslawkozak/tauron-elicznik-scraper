#!/usr/bin/env python

import requests
from requests import adapters
import ssl
import json
from urllib3 import poolmanager
import datetime
import configparser
from argparse import ArgumentParser
import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

parser = ArgumentParser()
parser.add_argument("-d", "--date", dest="date", default=(datetime.datetime.now() - datetime.timedelta(1)).strftime('%d.%m.%Y'), help="Chart day DD.MM.YYYY")
args = parser.parse_args()

config = configparser.ConfigParser()
config_path = os.path.dirname(__file__) + '/config.ini'
config.read(config_path)

username = config["tauron"]["username"]
password = config["tauron"]["password"]
meter_id = config["tauron"]["meter_id"]

payload = { 
                'username': username,
                'password': password ,
                'service': 'https://elicznik.tauron-dystrybucja.pl'
}

url = 'https://logowanie.tauron-dystrybucja.pl/login'
charturl = 'https://elicznik.tauron-dystrybucja.pl/index/charts'
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:52.0) Gecko/20100101 Firefox/52.0'} 

class TLSAdapter(adapters.HTTPAdapter):

    def init_poolmanager(self, connections, maxsize, block=False):
        """Create and initialize the urllib3 PoolManager."""
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        self.poolmanager = poolmanager.PoolManager(
                num_pools=connections,
                maxsize=maxsize,
                block=block,
                ssl_version=ssl.PROTOCOL_TLS,
                ssl_context=ctx)

session = requests.session()
session.mount('https://', TLSAdapter())

p = session.request("POST", url, data=payload, headers=headers)
p = session.request("POST", url, data=payload, headers=headers)

chart = {
	        #change timedelta to get data from another days (1 for yesterday)
                "dane[chartDay]": args.date,
                "dane[paramType]": "day",
                "dane[smartNr]": meter_id,
	        #comment if don't want generated energy data in JSON output:
                "dane[checkOZE]": "on"
}

r = session.request("POST", charturl, data=chart, headers=headers)
elicznik = json.loads(r.text)

client = influxdb_client.InfluxDBClient(url=config["influx"]["url"], token=config["influx"]["token"], org=config["influx"]["org"])
write_api = client.write_api(write_options=SYNCHRONOUS)

for usage in elicznik["dane"]["chart"]:
    entry = elicznik["dane"]["chart"][usage]
    date = datetime.datetime.strptime("{} {}".format(entry["Date"], int(entry["Hour"])-1), '%Y-%m-%d %H') + datetime.timedelta(hours=0)
    p = influxdb_client.Point("elicznik_hourly_usage").tag("meter_id", meter_id).time(date).field("usage", float(entry["EC"])*1000)
    write_api.write(bucket=config["influx"]["bucket"], org=config["influx"]["org"], record=p)

for usage in elicznik["dane"]["OZE"]:
    entry = elicznik["dane"]["OZE"][usage]
    date = datetime.datetime.strptime("{} {}".format(entry["Date"], int(entry["Hour"])-1), '%Y-%m-%d %H') + datetime.timedelta(hours=0)
    p = influxdb_client.Point("elicznik_hourly_production").tag("meter_id", meter_id).time(date).field("produced", float(entry["EC"])*1000)
    write_api.write(bucket=config["influx"]["bucket"], org=config["influx"]["org"], record=p)
