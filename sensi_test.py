import sys
import unittest
import logging
import service
import ConfigParser

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

config = ConfigParser.ConfigParser()
config.readfp(open('sensi_test.cfg'))

class SensiTest(unittest.TestCase):
    def setUp(self):
        self.data = []

    def data_callback(self, thermostat, status, data, updated_keys):
        self.data.append([thermostat, status, data, updated_keys])

    # Smoke test
    def test_connect(self):
        svc = service.SensiThermostatService(config.get('SectionOne','user'), config.get('SectionOne','password'))
        svc.start()
        svc.add_listener(service.dump_data)
        svc.add_listener(self.data_callback)
        svc.subscribe()
        for n in xrange(10):
            svc.poll()
            if self.data:
                break
        svc.disconnect()

if __name__ == '__main__':
    unittest.main()
