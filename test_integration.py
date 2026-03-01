"""
Integration tests for lambda_function.py.

These tests make real HTTP calls to the Ruuvi Network API and verify the
full pipeline: fetch → decode → render markup.

Credentials are loaded from config.py if present, otherwise from environment
variables. The tests are skipped if no credentials are found.

Run with:
    source env/bin/activate
    python3 -m unittest test_integration -v
"""

import json
import os
import re
import unittest

# Load credentials before importing lambda_function, which reads them at module
# load time. Prefer config.py (local dev) then fall back to environment vars.
def _load_credentials():
    if os.environ.get("RUUVI_TOKEN"):
        return True
    try:
        import config
        os.environ["RUUVI_TOKEN"] = config.ruuvi_token
        os.environ.setdefault("RUUVI_API_URL", config.ruuvi_api_url)
        return True
    except ImportError:
        return False

_credentials_available = _load_credentials()

if _credentials_available:
    import lambda_function


@unittest.skipUnless(
    _credentials_available,
    "No credentials found. Create config.py or set RUUVI_TOKEN in the environment.",
)
class TestGetMeasurementsIntegration(unittest.TestCase):
    """Tests that call the Ruuvi Network API directly."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.sensors = lambda_function.get_measurements()
        except Exception as e:
            raise unittest.SkipTest(f"Ruuvi API call failed: {e}")

    def test_returns_sensors(self):
        self.assertIsInstance(self.sensors, dict)
        self.assertGreater(len(self.sensors), 0, "No sensors returned from API")

    def test_expected_sensors_present(self):
        expected = ["Terrace", "Living room", "Bedroom", "Outside"]
        for name in expected:
            self.assertIn(name, self.sensors, f"Sensor '{name}' missing from API response")

    def test_each_sensor_has_temperature(self):
        for name, data in self.sensors.items():
            self.assertIn("temperature", data, f"Sensor '{name}' has no temperature field")

    def test_temperatures_are_numeric(self):
        for name, data in self.sensors.items():
            temp = data["temperature"]
            self.assertIsInstance(
                temp, (int, float), f"Sensor '{name}' temperature is not numeric: {temp!r}"
            )

    def test_temperatures_are_in_plausible_range(self):
        for name, data in self.sensors.items():
            temp = data["temperature"]
            self.assertGreater(temp, -50, f"Sensor '{name}': {temp}°C is unrealistically cold")
            self.assertLess(temp, 60, f"Sensor '{name}': {temp}°C is unrealistically hot")

    def test_prints_raw_sensor_data(self):
        """Not a real assertion — prints sensor readings for manual inspection."""
        print("\n--- Raw sensor data from Ruuvi API ---")
        for name, data in self.sensors.items():
            print(f"  {name}: {data['temperature']:.2f}°C")


@unittest.skipUnless(
    _credentials_available,
    "No credentials found. Create config.py or set RUUVI_TOKEN in the environment.",
)
class TestHandlerIntegration(unittest.TestCase):
    """Tests the full handler pipeline against the live Ruuvi API."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.response = lambda_function.handler({}, None)
            cls.body = json.loads(cls.response["body"])
        except Exception as e:
            raise unittest.SkipTest(f"Ruuvi API call failed: {e}")

    def test_status_code_is_200(self):
        self.assertEqual(self.response["statusCode"], 200)

    def test_content_type_header(self):
        self.assertEqual(self.response["headers"]["Content-Type"], "application/json")

    def test_body_has_markup_key(self):
        self.assertIn("markup", self.body)

    def test_markup_is_non_empty(self):
        self.assertTrue(self.body["markup"].strip())

    def test_markup_has_no_unreplaced_placeholders(self):
        self.assertNotIn("{{", self.body["markup"])

    def test_markup_is_valid_html_fragment(self):
        markup = self.body["markup"]
        self.assertIn("<div", markup)
        self.assertIn("</div>", markup)
        self.assertIn("title_bar", markup)

    def test_markup_contains_temperature_values(self):
        temps = re.findall(r"-?\d+\.\d°", self.body["markup"])
        self.assertGreaterEqual(len(temps), 4, f"Expected at least 4 temperatures, found: {temps}")

    def test_markup_temperatures_are_in_plausible_range(self):
        temps = re.findall(r"(-?\d+\.\d)°", self.body["markup"])
        for t in temps:
            val = float(t)
            self.assertGreater(val, -50, f"Temperature {val}°C in markup is unrealistically cold")
            self.assertLess(val, 60, f"Temperature {val}°C in markup is unrealistically hot")

    def test_prints_rendered_markup(self):
        """Not a real assertion — prints the rendered markup for visual inspection."""
        print("\n--- Rendered markup ---")
        print(self.body["markup"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
