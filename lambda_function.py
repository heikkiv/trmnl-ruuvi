import os
import json
import logging
import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import requests
import ruuvi_decoders

DEFAULT_TZ = "Europe/Helsinki"

logger = logging.getLogger()
logger.setLevel(logging.INFO)

RUUVI_TOKEN = os.environ["RUUVI_TOKEN"]
RUUVI_API_URL = os.environ.get(
    "RUUVI_API_URL",
    "https://network.ruuvi.com/sensors-dense?sharedToMe=true&measurements=true&alerts=true&sharedToOthers=true",
)
PLUGIN_NAME = os.environ.get("PLUGIN_NAME", "Ruuvi")

# ---------------------------------------------------------------------------
# Markup templates
# ---------------------------------------------------------------------------

MARKUP_FULL = """\
<div class="view view--full">
  <div class="layout gap--space-between">
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
    <div class="layout layout--col gap--space-between">
      <div class="item">
        <div class="meta"></div>
        <div class="content">
          <span class="value value--tnums value--large">{{mokki_outside}}</span>
          <span class="label">Mökki ulkona</span>
        </div>
      </div>
      <div class="w-full b-h-gray-5"></div>
      <div class="item">
        <div class="meta"></div>
        <div class="content">
          <span class="value value--tnums value--large">{{mokki_inside}}</span>
          <span class="label">Mökki olohuone</span>
        </div>
      </div>
      <div class="w-full b-h-gray-5"></div>
      <div class="item">
        <div class="meta"></div>
        <div class="content">
          <span class="value value--tnums value--large">{{mokki_basement}}</span>
          <span class="label">Mökki kellari</span>
        </div>
      </div>
    </div>
  </div>

  <div class="title_bar">
    <img class="image" src="https://usetrmnl.com/images/plugins/trmnl--render.svg">
    <span class="title">{{plugin_name}}</span>
    <span class="instance">Lämpötila koti &mdash; {{updated_at}}</span>
  </div>
</div>
"""

MARKUP_HALF_VERTICAL = """\
<div class="view view--half_vertical">
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
    <span class="instance">Lämpötila koti &mdash; {{updated_at}}</span>
  </div>
</div>
"""

MARKUP_HALF_HORIZONTAL = """\
<div class="view view--half_horizontal">
  <div class="layout gap--space-between">
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--large" data-value-format="true">{{outside}}</span>
        <span class="label">Ulkona</span>
      </div>
    </div>
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--large">{{livingroom}}</span>
        <span class="label">Olohuone</span>
      </div>
    </div>
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--large">{{bedroom}}</span>
        <span class="label">Makuuhuone</span>
      </div>
    </div>
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--large">{{study}}</span>
        <span class="label">Auroran huone</span>
      </div>
    </div>
  </div>

  <div class="title_bar">
    <img class="image" src="https://usetrmnl.com/images/plugins/trmnl--render.svg">
    <span class="title">{{plugin_name}}</span>
    <span class="instance">Lämpötila koti &mdash; {{updated_at}}</span>
  </div>
</div>
"""

MARKUP_QUADRANT = """\
<div class="view view--quadrant">
  <div class="layout layout--col gap--space-between">
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--large" data-value-format="true">{{outside}}</span>
        <span class="label">Ulkona</span>
      </div>
    </div>
    <div class="w-full b-h-gray-5"></div>
    <div class="item">
      <div class="meta"></div>
      <div class="content">
        <span class="value value--tnums value--small">{{livingroom}}</span>
        <span class="label">Olohuone</span>
      </div>
    </div>
  </div>

  <div class="title_bar">
    <img class="image" src="https://usetrmnl.com/images/plugins/trmnl--render.svg">
    <span class="title">{{plugin_name}}</span>
    <span class="instance">Lämpötila koti &mdash; {{updated_at}}</span>
  </div>
</div>
"""

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

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


def resolve_tz(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unknown time zone %r, falling back to %s", name, DEFAULT_TZ)
        return ZoneInfo(DEFAULT_TZ)


def get_template_vars(sensors, tz):
    now = datetime.datetime.now(tz).strftime("%H:%M")
    return {
        "outside":        fmt(sensors["Terrace"]["temperature"]),
        "livingroom":     fmt(sensors["Living room"]["temperature"]),
        "bedroom":        fmt(sensors["Bedroom"]["temperature"]),
        "study":          fmt(sensors["Outside"]["temperature"]),
        "mokki_outside":  fmt(sensors["Mökki ulkona"]["temperature"]),
        "mokki_inside":   fmt(sensors["Mökki olohuone"]["temperature"]),
        "mokki_basement": fmt(sensors["Mökki kellari"]["temperature"]),
        "plugin_name":    PLUGIN_NAME,
        "updated_at":     now,
    }


def build_markup(template, sensors, tz):
    markup = template
    for key, value in get_template_vars(sensors, tz).items():
        markup = markup.replace("{{" + key + "}}", value)
    return markup


def handler(event, context):
    sensors = get_measurements()
    logger.info("Fetched sensors: %s", list(sensors.keys()))

    tz_name = (event.get("queryStringParameters") or {}).get("tz", DEFAULT_TZ)
    tz = resolve_tz(tz_name)

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "markup":                 build_markup(MARKUP_FULL, sensors, tz),
            "markup_half_horizontal": build_markup(MARKUP_HALF_HORIZONTAL, sensors, tz),
            "markup_half_vertical":   build_markup(MARKUP_HALF_VERTICAL, sensors, tz),
            "markup_quadrant":        build_markup(MARKUP_QUADRANT, sensors, tz),
        }),
    }
