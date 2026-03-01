import json
import os
import unittest
from unittest.mock import MagicMock, patch

# Set required env vars before importing the module, which reads them at load time
os.environ.setdefault("RUUVI_TOKEN", "test-token")
os.environ.setdefault("PLUGIN_NAME", "Test Plugin")

import lambda_function

SAMPLE_SENSORS = {
    "Terrace": {"temperature": 5.23},
    "Living room": {"temperature": 21.5},
    "Bedroom": {"temperature": 19.0},
    "Outside": {"temperature": 18.5},
}


class TestFmt(unittest.TestCase):
    def test_one_decimal_place(self):
        self.assertEqual(lambda_function.fmt(23.456), "23.5°")

    def test_rounds_up(self):
        self.assertEqual(lambda_function.fmt(23.46), "23.5°")

    def test_negative_temperature(self):
        self.assertEqual(lambda_function.fmt(-5.0), "-5.0°")

    def test_zero(self):
        self.assertEqual(lambda_function.fmt(0.0), "0.0°")


class TestBuildMarkup(unittest.TestCase):
    def setUp(self):
        self.markup = lambda_function.build_markup(SAMPLE_SENSORS)

    def test_outside_temperature(self):
        self.assertIn("5.2°", self.markup)

    def test_livingroom_temperature(self):
        self.assertIn("21.5°", self.markup)

    def test_bedroom_temperature(self):
        self.assertIn("19.0°", self.markup)

    def test_study_temperature(self):
        self.assertIn("18.5°", self.markup)

    def test_plugin_name(self):
        self.assertIn("Test Plugin", self.markup)

    def test_no_unreplaced_placeholders(self):
        self.assertNotIn("{{", self.markup)

    def test_is_valid_html_fragment(self):
        self.assertIn("<div", self.markup)
        self.assertIn("</div>", self.markup)


class TestGetMeasurements(unittest.TestCase):
    def _make_api_response(self, sensors):
        """Build a minimal Ruuvi API response for the given list of (name, hex_payload) tuples."""
        return {
            "data": {
                "sensors": [
                    {"name": name, "measurements": [{"data": "FF9904" + payload}]}
                    for name, payload in sensors
                ]
            }
        }

    @patch("lambda_function.ruuvi_decoders.Df5Decoder")
    @patch("lambda_function.requests.get")
    def test_returns_all_sensors(self, mock_get, mock_decoder_class):
        mock_decoder_class.return_value.decode_data.return_value = {"temperature": 21.5}
        mock_get.return_value.json.return_value = self._make_api_response(
            [("Terrace", "AABBCC"), ("Living room", "DDEEFF")]
        )

        result = lambda_function.get_measurements()

        self.assertIn("Terrace", result)
        self.assertIn("Living room", result)

    @patch("lambda_function.ruuvi_decoders.Df5Decoder")
    @patch("lambda_function.requests.get")
    def test_decodes_sensor_data(self, mock_get, mock_decoder_class):
        decoded = {"temperature": 21.5, "humidity": 50}
        mock_decoder_class.return_value.decode_data.return_value = decoded
        mock_get.return_value.json.return_value = self._make_api_response(
            [("Terrace", "AABBCC")]
        )

        result = lambda_function.get_measurements()

        self.assertEqual(result["Terrace"]["temperature"], 21.5)

    @patch("lambda_function.ruuvi_decoders.Df5Decoder")
    @patch("lambda_function.requests.get")
    def test_strips_prefix_before_decoding(self, mock_get, mock_decoder_class):
        """Verifies only the payload after FF9904 is passed to the decoder."""
        mock_decoder_class.return_value.decode_data.return_value = {"temperature": 1.0}
        mock_get.return_value.json.return_value = self._make_api_response(
            [("Terrace", "PAYLOAD")]
        )

        lambda_function.get_measurements()

        mock_decoder_class.return_value.decode_data.assert_called_once_with("PAYLOAD")

    @patch("lambda_function.requests.get")
    def test_raises_on_http_error(self, mock_get):
        mock_get.return_value.raise_for_status.side_effect = Exception("401 Unauthorized")

        with self.assertRaises(Exception):
            lambda_function.get_measurements()

    @patch("lambda_function.ruuvi_decoders.Df5Decoder")
    @patch("lambda_function.requests.get")
    def test_sends_auth_header(self, mock_get, mock_decoder_class):
        mock_decoder_class.return_value.decode_data.return_value = {"temperature": 1.0}
        mock_get.return_value.json.return_value = self._make_api_response([])

        lambda_function.get_measurements()

        _, kwargs = mock_get.call_args
        self.assertIn("Authorization", kwargs.get("headers", {}))
        self.assertIn("test-token", kwargs["headers"]["Authorization"])


class TestHandler(unittest.TestCase):
    @patch("lambda_function.get_measurements", return_value=SAMPLE_SENSORS)
    def test_returns_200(self, _):
        response = lambda_function.handler({}, None)
        self.assertEqual(response["statusCode"], 200)

    @patch("lambda_function.get_measurements", return_value=SAMPLE_SENSORS)
    def test_content_type_header(self, _):
        response = lambda_function.handler({}, None)
        self.assertEqual(response["headers"]["Content-Type"], "application/json")

    @patch("lambda_function.get_measurements", return_value=SAMPLE_SENSORS)
    def test_body_is_valid_json(self, _):
        response = lambda_function.handler({}, None)
        body = json.loads(response["body"])
        self.assertIsInstance(body, dict)

    @patch("lambda_function.get_measurements", return_value=SAMPLE_SENSORS)
    def test_body_contains_markup_key(self, _):
        response = lambda_function.handler({}, None)
        body = json.loads(response["body"])
        self.assertIn("markup", body)

    @patch("lambda_function.get_measurements", return_value=SAMPLE_SENSORS)
    def test_markup_contains_sensor_temperatures(self, _):
        response = lambda_function.handler({}, None)
        body = json.loads(response["body"])
        self.assertIn("5.2°", body["markup"])
        self.assertIn("21.5°", body["markup"])

    @patch("lambda_function.get_measurements", side_effect=Exception("Ruuvi API down"))
    def test_propagates_ruuvi_errors(self, _):
        with self.assertRaises(Exception, msg="Ruuvi API down"):
            lambda_function.handler({}, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
