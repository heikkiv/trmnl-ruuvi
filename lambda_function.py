import os
import json
import logging
import requests
import ruuvi_decoders

logger = logging.getLogger()
logger.setLevel(logging.INFO)

RUUVI_TOKEN = os.environ["RUUVI_TOKEN"]
RUUVI_API_URL = os.environ.get(
    "RUUVI_API_URL",
    "https://network.ruuvi.com/sensors-dense?sharedToMe=true&measurements=true&alerts=true&sharedToOthers=true",
)
PLUGIN_NAME = os.environ.get("PLUGIN_NAME", "Ruuvi")

MARKUP_TEMPLATE = """\
<div class="layout layout--col gap--space-between">
  <div class="item">
    <div class="meta"></div>
    <div class="content">
      <span class="value value--tnums value--xxlarge" data-value-format="true">{{outside}}</span>
      <span class="label">Ulkona</span>
    </div>
  </div>
  <div class="w-full b-h-gray-5"></div>
  <div class="item">
    <div class="meta"></div>
    <div class="content">
      <span class="value value--tnums value--large">{{livingroom}}</span>
      <span class="label">Olohuone</span>
    </div>
  </div>
  <div class="w-full b-h-gray-5"></div>
  <div class="grid grid--cols-2">
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--small">{{bedroom}}</span>
        <span class="label">Makuuhuone</span>
      </div>
    </div>
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--small">{{study}}</span>
        <span class="label">Auroran huone</span>
      </div>
    </div>
  </div>
</div>

<div class="title_bar">
  <img class="image" src="https://usetrmnl.com/images/plugins/trmnl--render.svg">
  <span class="title">{{plugin_name}}</span>
  <span class="instance">Lämpötila koti</span>
</div>
"""


def get_measurements():
    headers = {"Authorization": "Bearer " + RUUVI_TOKEN}
    r = requests.get(RUUVI_API_URL, headers=headers)
    r.raise_for_status()

    sensors = {}
    decoder = ruuvi_decoders.Df5Decoder()
    for sensor in r.json()["data"]["sensors"]:
        name = sensor["name"]
        data = sensor["measurements"][0]["data"]
        data = data[data.index("FF9904") + 6:]
        sensors[name] = decoder.decode_data(data)
    return sensors


def fmt(value):
    return f"{value:.1f}°"


def build_markup(sensors):
    markup = MARKUP_TEMPLATE
    markup = markup.replace("{{outside}}", fmt(sensors["Terrace"]["temperature"]))
    markup = markup.replace("{{livingroom}}", fmt(sensors["Living room"]["temperature"]))
    markup = markup.replace("{{bedroom}}", fmt(sensors["Bedroom"]["temperature"]))
    markup = markup.replace("{{study}}", fmt(sensors["Outside"]["temperature"]))
    markup = markup.replace("{{plugin_name}}", PLUGIN_NAME)
    return markup


def handler(event, context):
    sensors = get_measurements()
    logger.info("Fetched sensors: %s", list(sensors.keys()))

    markup = build_markup(sensors)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"markup": markup}),
    }
