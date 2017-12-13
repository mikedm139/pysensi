import sys
import unittest
import logging
import service
import ConfigParser

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

config_parser = ConfigParser.ConfigParser()
config_parser.read(["sensi_test.cfg"])
config = config_parser.defaults()

class SensiTest(unittest.TestCase):
    def setUp(self):
        self.data = []

    def data_callback(self, thermostat, status, data, updated_keys):
        self.data.append([thermostat, status, data, updated_keys])

    # Smoke test
    def test_connect(self):
        svc = sensi.service.SensiThermostatService(config["user"], config["password"])
        svc.start()
        svc.add_listener(sensi.service.dump_data)
        svc.add_listener(self.data_callback)
        svc.subscribe()
        for n in xrange(10):
            svc.poll()
            if self.data:
                break
        svc.disconnect()

if __name__ == '__main__':
    unittest.main()
