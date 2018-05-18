import sys
import calendar
import time
import requests
import json
import jsonpath_rw
import math
import random
import logging

from pprint import pprint

BASE_URL = "https://bus-serv.sensicomfort.com"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) " \
           "Chrome/45.0.2454.101 Safari/537.36"

ACCEPTED_MIMETYPE = 'application/json; version=1, */*; q=0.01'

DEFAULT_HEADERS = {
    'User-Agent': USER_AGENT,
    'X-Requested-With': 'XMLHttpRequest',  # needed to get cookies instead of token
    'Accept': ACCEPTED_MIMETYPE,
    'Origin': 'https://mythermostat.sensicomfort.com',
    'Referer': 'https://mythermostat.sensicomfort.com',
}

REALTIME_HEADERS = {
    'X-Requested-With': 'XMLHttpRequest',  # needed to get cookies instead of token
    'Allow-Encoding': 'gzip, deflate, sdch',
    'Accept': ACCEPTED_MIMETYPE,
    'Accept-Language': 'en-US,en;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'User-Agent': USER_AGENT,
    'Origin': 'https://mythermostat.sensicomfort.com',
    'Referer': 'https://mythermostat.sensicomfort.com',
}

class SensiThermostatService(object):
    def __init__(self, username, password, temperature_scale):
        self.username = username
        self.password = password
        self.temperature_scale = temperature_scale
        self.connection_token = None
        self.session = requests.session()
        self.log = logging.getLogger(type(self).__name__)
        self.authorized = False
        self.connected = False
        self.messageId = None
        self.groupsToken = None
        self.subscription_id = 0
        self.listeners = []
        self.thermostats = []
        self.thermostat_status = {}
        self.thermostat_data = {}

    def _authorize(self):
        payload = {
            'UserName': self.username,
            'Password': self.password
        }
        response = self.session.post(
                BASE_URL + "/api/authorize",
                json=payload,
                headers=DEFAULT_HEADERS)
        self.authorized = response.status_code == 200
        if not self.authorized:
            self.log.error("authorization failed")
        else:
            self.log.debug("authorize: status=%d", response.status_code)

    def _negotiate(self):
        params = {'_': self._unix_timestamp()}
        response = self.session.get(
                BASE_URL + "/realtime/negotiate",
                headers=DEFAULT_HEADERS,
                params=params)
        self.connection_token = response.json()['ConnectionToken']
        self.log.debug("negotiate: status=%d", response.status_code)

    def _connect(self):
        params = {
            'transport': 'longPolling',
            'connectionToken': self.connection_token,
            'connectionData': '[{"name": "thermostat-v1"}]',
            'tid': int(math.floor(random.random() * 11)),
            '_': self._unix_timestamp(),
        }

        response = self.session.get(
            BASE_URL + "/realtime/connect",
            params=params,
            headers=REALTIME_HEADERS)

        self.connected = response.status_code == 200
        self.messageId = response.json()["C"]
        self.log.debug("connect, status=%d, msgid=%s", response.status_code, self.messageId)

    def _request_thermostats_info(self):
        response = self.session.get(BASE_URL + "/api/thermostats", headers=DEFAULT_HEADERS)
        self.thermostats = response.json()

    def _merge(self, a, b, updated_keys=None, path=None):
        def key_path(k):
            return path is None and k or (path + "." + k)
        if updated_keys is None:
            updated_keys = []
        for key in b:
            if key in a:
                a_value = a[key]
                b_value = b[key]
                if isinstance(a_value, dict) and isinstance(b_value, dict):
                    self._merge(a_value, b_value, updated_keys, key_path(key))
                elif isinstance(a_value, list) and isinstance(b_value, list):
                    if len(a_value) == len(b_value):
                        path_base = key_path(key)
                        for i in xrange(len(a_value)):
                            self._merge(a_value[i], b_value[i], updated_keys, path_base + "[" + str(i) + "]")
                elif a_value != b_value:
                    a[key] = b_value
                    updated_keys.append((key_path(key), a_value, b_value))
            else:
                b_value = b[key]
                a[key] = b_value
                updated_keys.append((key_path(key), None, b_value))
        return updated_keys

    @staticmethod
    def _unix_timestamp():
        return calendar.timegm(time.gmtime()) * 1000

    def subscribe(self):
        for thermostat in self.thermostats:
            params = {
                'transport': 'longPolling',
                'connectionToken': self.connection_token,
            }

            payload = {
                'data': json.dumps({
                    "H": "thermostat-v1",
                    "M": "Subscribe",
                    "A": [thermostat.get("ICD")],
                    "I": self.subscription_id
                }, separators=(',', ':'))
            }

            response = self.session.post(
                BASE_URL + "/realtime/send",
                data=payload,
                params=params,
                headers=REALTIME_HEADERS
            )

            if response.status_code == 200:
                self.subscription_id += 1

            self.log.debug("subscribe: status=%d, icd=%s, sub_id=%s",
                           response.status_code, thermostat.get("ICD"), response.json()["I"])

    def poll(self):
        params = {
            'transport': 'longPolling',
            'connectionToken': self.connection_token,
            'connectionData': '[{"name": "thermostat-v1"}]',
            'messageId': self.messageId,
            'tid': int(math.floor(random.random() * 11)),
            '_': self._unix_timestamp(),
        }

        if self.groupsToken:
            params['groupsToken'] = self.groupsToken

        response = self.session.get(
            BASE_URL + "/realtime/poll",
            params=params,
            headers=REALTIME_HEADERS)

        response_json = response.json()
        self.log.info("poll: status=%d, msgId=%s", response.status_code, self.messageId)

        if response.status_code == 200:
            self.messageId = response_json.get("C")
            if "G" in response_json:
                self.groupsToken = response_json.get("G")

        m = response_json["M"]
        if len(m) > 0:
            m0 = response_json["M"][0]
            device_status = m0["M"]
            device_id = "A" in m0 and m0["A"][0] or None
            self.log.info("device data received: icd=%s, status=%s", device_id, device_status)
            if device_status in ["online", "update"]:
                device_data = m0["A"][1]
                self.thermostat_status[device_id] = device_status
                if str(device_id) in self.thermostat_data:
                    data = self.thermostat_data[device_id]
                    updated_keys = self._merge(data, device_data)
                else:
                    data = device_data
                    updated_keys = None
                self.thermostat_data[str(device_id)] = data
                for listener in self.listeners:
                    listener(self._get_thermostat_with_icd(device_id), device_status, device_data, updated_keys)

    def start(self):
        self._authorize()
        if self.authorized:
            self._request_thermostats_info()
            self._negotiate()
            self._connect()

    def disconnect(self):
        params = {
            'transport': 'longPolling',
            'connectionToken': self.connection_token,
        }

        response = self.session.get(
            BASE_URL + "/realtime/abort",
            params=params,
            headers=REALTIME_HEADERS)

        if response.status_code == 200:
            self.connected = False

        self.log.info("disconnect: status=%d", response.status_code)

    def add_listener(self, listener):
        self.listeners.append(listener)

    def weather(self, icd):
        response = self.session.get(
                BASE_URL + "/api/weather/{}".format(icd),
                headers=DEFAULT_HEADERS)
        return response.text

    def ping(self):
        params = {'_': self._unix_timestamp()}
        response = self.session.get(
                BASE_URL + "/realtime/ping",
                params=params,
                headers=DEFAULT_HEADERS)
        return response.json()['Response']

    def _get_thermostat_with_icd(self, icd):
        for thermostat in self.thermostats:
            if thermostat.get("ICD") == icd:
                return thermostat
        return None

    def set_heat(self, temperature, icd=None):
        if icd is None:
            if len(self.thermostats) == 1:
                icd = self.thermostats[0]["ICD"]
            else:
                raise Exception("Multiple thermostats. Must provide ICD.")

        params = {
            'transport': 'longPolling',
            'connectionToken': self.connection_token,
        }

        payload = {
            'data': json.dumps({
                'H': 'thermostat-v1',
                'M': 'SetHeat',
                'A': [icd, temperature, self.temperature_scale],
                'I': 1
            }, separators=(',', ':'))
        }

        response = self.session.post(
            BASE_URL + "/realtime/send",
            data=payload,
            params=params,
            headers=REALTIME_HEADERS)

        print 'request headers:'
        print "\n".join("{}: {}".format(k, v) for k, v in response.request.headers.iteritems())

#
#
#

def debug_http():
    logging.root.setLevel(logging.DEBUG)
    # These two lines enable debugging at httplib level (requests->urllib3->http.client)
    # You will see the REQUEST, including HEADERS and DATA, and RESPONSE with HEADERS but without DATA.
    # The only thing missing will be the response.body which is not logged.
    try:
        import http.client as http_client
    except ImportError:
        # Python 2
        import httplib as http_client
    http_client.HTTPConnection.debuglevel = 1

    # You must initialize logging, otherwise you'll not see debug output.
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

def get_json_value(json_data, path):
    contexts = jsonpath_rw.parse(path).find(json_data)
    if contexts:
        return contexts[0].value
    return None

def dump_data(thermostat, status, data, updated_keys):
    pprint([status, thermostat['DeviceName'], thermostat['ICD']])
    pprint(['Temp:', get_json_value(data, "OperationalStatus.Temperature.C"), 'C',  get_json_value(data, "OperationalStatus.Temperature.F"), 'F'])
    pprint(['Running:', get_json_value(data, "OperationalStatus.Running.Mode")])
    pprint(['Battery:', get_json_value(data, "OperationalStatus.BatteryVoltage")])
    pprint(['UpdatedKeys', updated_keys])
    print "---------"

