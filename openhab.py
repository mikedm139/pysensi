import logging
import requests
import sys
import time

from sensi.service import get_json_value, SensiThermostatService

LOG = logging.getLogger("openhab")

rest_endpoint = None
thermostats = []

def publish_update(item_name, value):
    headers = {
        "Content-Type": "text/plain",
    }
    return requests.put("{}/{}/state".format(rest_endpoint, item_name), data=str(value), headers=headers)


_ITEMS = [
    ("Sensi_Name_{id}", lambda thermostat, status, data, updated_keys: updated_keys is None and thermostat["DeviceName"] or None),
    ("Sensi_ICD_{id}", lambda thermostat, status, data, updated_keys: updated_keys is None and thermostat["ICD"] or None),
    ("Sensi_Status_{id}", lambda thermostat, status, data, updated_keys: (status in ["online", "update"]) and "online" or status),
    ("Sensi_Temperature_{id}", "OperationalStatus.Temperature.F"),
    ("Sensi_Humidity_{id}", "OperationalStatus.Humidity"),
    ("Sensi_RunningMode_{id}", "OperationalStatus.Running.Mode"),
    ("Sensi_BatteryVoltage_{id}", "OperationalStatus.BatteryVoltage"),
]


def update_items(thermostat, status, data, updated_keys):
    icd = thermostat.get("ICD")
    try:
        device_suffix = thermostats.index(icd) + 1
    except ValueError:
        LOG.error("Unknown ICD: %s", icd)
        return
    for item in _ITEMS:
        key = item[0].format(id=device_suffix)
        value = None
        if hasattr(item[1], "__call__"):
            value = item[1](thermostat, status, data, updated_keys)
        elif updated_keys is None or item[0] in updated_keys:
            value = get_json_value(data, item[1])
        if value is not None:
            LOG.debug("publishing: %s status=%s %s=%s", icd, status, key, value)
            response = publish_update(key, value)
            LOG.info("published: %s key=%s status=%s", icd, key, response.status_code)
        else:
            LOG.debug("%s: no value for %s", icd, key)

def _main(args):
    global rest_endpoint, thermostats
    rest_endpoint = "http://{}:{}/rest/items".format(args.host, args.port)
    thermostats = args.thermostats
    if args.log:
        logging.basicConfig(filename=args.log)
    else:
        logging.basicConfig(stream=sys.stdout)
    logging.getLogger("SensiThermostatService").setLevel(args.debug and logging.DEBUG or logging.INFO)
    LOG.setLevel(args.debug and logging.DEBUG or logging.INFO)
    sensi_service = SensiThermostatService(args.username, args.password)
    sensi_service.start()
    try:
        sensi_service.subscribe()
        sensi_service.add_listener(update_items)
        n = 0
        while True:
            sensi_service.poll()
            time.sleep(args.period)
            n += 1
            if n == args.count:
                break
    finally:
        sensi_service.disconnect()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="OpenHAB hostname")
    parser.add_argument("username")
    parser.add_argument("password")
    parser.add_argument("thermostats", nargs="+", help="ICDs for monitored thermostats")
    parser.add_argument("--port", default=8080)
    parser.add_argument("--period", type=float, default=60.0, help="polling period in seconds (float)")
    parser.add_argument("--count", type=int, help="number of polls (-1 is infinite)", default=-1)
    parser.add_argument("--log", help="name of log file (default to console)")
    parser.add_argument("--debug", action="store_true")
    _main(parser.parse_args())
