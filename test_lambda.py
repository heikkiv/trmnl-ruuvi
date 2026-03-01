import json
import os
import unittest
from unittest.mock import patch

# Set required env vars before importing the module, which reads them at load time
os.environ.setdefault("RUUVI_TOKEN", "test-token")
os.environ.setdefault("PLUGIN_NAME", "Test Plugin")

import lambda_function

SAMPLE_SENSORS = {
    "Terrace":          {"temperature": 5.23},
    "Living room":      {"temperature": 21.5},
    "Bedroom":          {"temperature": 19.0},
    "Outside":          {"temperature": 18.5},
    "Mökki ulkona":     {"temperature": 3.1},
    "Mökki olohuone":   {"temperature": 17.8},
    "Mökki kellari":    {"temperature": 10.4},
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


class TestGetTemplateVars(unittest.TestCase):
    def setUp(self):
        self.vars = lambda_function.get_template_vars(SAMPLE_SENSORS)

    def test_all_keys_present(self):
        expected = {"outside", "livingroom", "bedroom", "study",
                    "mokki_outside", "mokki_inside", "mokki_basement",
                    "plugin_name", "updated_at"}
        self.assertEqual(set(self.vars.keys()), expected)

    def test_values_are_formatted(self):
        self.assertEqual(self.vars["outside"], "5.2°")
        self.assertEqual(self.vars["livingroom"], "21.5°")
        self.assertEqual(self.vars["mokki_outside"], "3.1°")

    def test_plugin_name(self):
        self.assertEqual(self.vars["plugin_name"], "Test Plugin")


class TestBuildMarkup(unittest.TestCase):
    def _build(self, template):
        return lambda_function.build_markup(template, SAMPLE_SENSORS)

    def test_half_vertical_no_placeholders(self):
        self.assertNotIn("{{", self._build(lambda_function.MARKUP_HALF_VERTICAL))

    def test_half_horizontal_no_placeholders(self):
        self.assertNotIn("{{", self._build(lambda_function.MARKUP_HALF_HORIZONTAL))

    def test_full_no_placeholders(self):
        self.assertNotIn("{{", self._build(lambda_function.MARKUP_FULL))

    def test_quarter_no_placeholders(self):
        self.assertNotIn("{{", self._build(lambda_function.MARKUP_QUARTER))

    def test_half_vertical_home_temps(self):
        markup = self._build(lambda_function.MARKUP_HALF_VERTICAL)
        self.assertIn("5.2°", markup)    # outside
        self.assertIn("21.5°", markup)   # livingroom
        self.assertIn("19.0°", markup)   # bedroom
        self.assertIn("18.5°", markup)   # study

    def test_full_home_and_cottage_temps(self):
        markup = self._build(lambda_function.MARKUP_FULL)
        self.assertIn("5.2°", markup)    # outside
        self.assertIn("21.5°", markup)   # livingroom
        self.assertIn("3.1°", markup)    # mokki_outside
        self.assertIn("17.8°", markup)   # mokki_inside
        self.assertIn("10.4°", markup)   # mokki_basement

    def test_quarter_key_temps(self):
        markup = self._build(lambda_function.MARKUP_QUARTER)
        self.assertIn("5.2°", markup)    # outside
        self.assertIn("21.5°", markup)   # livingroom

    def test_half_horizontal_home_temps(self):
        markup = self._build(lambda_function.MARKUP_HALF_HORIZONTAL)
        for temp in ("5.2°", "21.5°", "19.0°", "18.5°"):
            self.assertIn(temp, markup)

    def test_plugin_name_in_all_views(self):
        for template in (lambda_function.MARKUP_FULL,
                         lambda_function.MARKUP_HALF_HORIZONTAL,
                         lambda_function.MARKUP_HALF_VERTICAL,
                         lambda_function.MARKUP_QUARTER):
            with self.subTest(template=template[:30]):
                self.assertIn("Test Plugin", self._build(template))


class TestGetMeasurements(unittest.TestCase):
    def _make_api_response(self, sensors):
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
        mock_decoder_class.return_value.decode_data.return_value = {"temperature": 21.5}
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
    def setUp(self, _):
        self.response = lambda_function.handler({}, None)
        self.body = json.loads(self.response["body"])

    def test_returns_200(self):
        self.assertEqual(self.response["statusCode"], 200)

    def test_content_type_header(self):
        self.assertEqual(self.response["headers"]["Content-Type"], "application/json")

    def test_body_contains_all_markup_keys(self):
        self.assertIn("markup", self.body)
        self.assertIn("markup_half_horizontal", self.body)
        self.assertIn("markup_half_vertical", self.body)
        self.assertIn("markup_quarter", self.body)

    def test_full_markup_has_cottage_temps(self):
        self.assertIn("3.1°", self.body["markup"])   # mokki_outside
        self.assertIn("17.8°", self.body["markup"])  # mokki_inside
        self.assertIn("10.4°", self.body["markup"])  # mokki_basement

    def test_half_vertical_markup_has_home_temps(self):
        markup = self.body["markup_half_vertical"]
        for temp in ("5.2°", "21.5°", "19.0°", "18.5°"):
            self.assertIn(temp, markup)

    def test_quarter_markup_excludes_cottage_temps(self):
        markup = self.body["markup_quarter"]
        self.assertIn("5.2°", markup)
        self.assertIn("21.5°", markup)
        self.assertNotIn("3.1°", markup)

    def test_no_placeholders_in_any_markup(self):
        for key in ("markup", "markup_half_horizontal", "markup_half_vertical", "markup_quarter"):
            with self.subTest(key=key):
                self.assertNotIn("{{", self.body[key])

    @patch("lambda_function.get_measurements", side_effect=Exception("Ruuvi API down"))
    def test_propagates_ruuvi_errors(self, _):
        with self.assertRaises(Exception, msg="Ruuvi API down"):
            lambda_function.handler({}, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
