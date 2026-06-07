#!/usr/bin/env python3
"""
Local preview server for the TRMNL markup.

Fetches live sensor data from the Ruuvi API once per request and renders
all three view sizes on a single page so you can compare them side by side.

Credentials are loaded from config.py if present, otherwise from the
RUUVI_TOKEN environment variable.

Run with:
    source env/bin/activate
    python3 preview_server.py

Then open http://localhost:8080 in your browser.
"""

import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

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

if not _load_credentials():
    print("Error: no credentials found.")
    print("Create config.py or set the RUUVI_TOKEN environment variable.")
    sys.exit(1)

import lambda_function

PORT = 8080

PAGE = """\
<!DOCTYPE html>
<html lang="fi">
<head>
  <meta charset="utf-8">
  <title>TRMNL Preview</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #c8c8c8;
      min-height: 100vh;
      padding: 32px 24px;
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 40px;
    }}

    /* --- Toolbar -------------------------------------------------------- */
    .toolbar {{
      display: flex;
      align-items: center;
      gap: 12px;
      background: rgba(255,255,255,0.6);
      border-radius: 8px;
      padding: 8px 16px;
      font-size: 13px;
      color: #333;
      align-self: stretch;
      justify-content: space-between;
    }}
    .toolbar a {{
      color: #222;
      text-decoration: none;
      border: 1px solid #aaa;
      border-radius: 5px;
      padding: 4px 12px;
    }}
    .toolbar a:hover {{ background: rgba(0,0,0,0.1); }}

    /* --- View section -------------------------------------------------- */
    .view-section {{
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }}
    .view-label {{
      font-size: 12px;
      font-weight: 600;
      color: #555;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    /* --- Simulated e-ink screens --------------------------------------- */
    .screen {{
      background: #fff;
      border: 2px solid #555;
      border-radius: 4px;
      box-shadow: 0 6px 24px rgba(0,0,0,0.3);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      color: #000;
    }}
    .screen-full             {{ width: 800px; height: 480px; padding: 20px 20px 12px; }}
    .screen-half-horizontal  {{ width: 800px; height: 240px; padding: 14px 20px 10px; }}
    .screen-half-vertical    {{ width: 400px; height: 480px; padding: 20px 20px 12px; }}
    .screen-quadrant         {{ width: 400px; height: 240px; padding: 14px 14px 10px; }}

    /* --- TRMNL CSS approximation --------------------------------------- */
    .screen .view {{
      display: flex;
      flex-direction: column;
      flex: 1;
      min-height: 0;
      min-width: 0;
      width: 100%;
    }}
    .screen .layout {{
      display: flex;
      flex: 1;
      min-height: 0;
      min-width: 0;
    }}
    .screen .layout--col        {{ flex-direction: column; }}
    .screen .gap--space-between {{ justify-content: space-between; }}

    /* Side-by-side columns in the full view each take equal width */
    .screen .layout > .layout {{ flex: 1; }}

    .screen .item {{
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}
    .screen .meta    {{ display: none; }}
    .screen .content {{ display: flex; flex-direction: column; gap: 4px; }}

    .screen .value {{
      font-weight: 700;
      line-height: 1;
      font-variant-numeric: tabular-nums;
      letter-spacing: -0.02em;
    }}

    /* Font sizes per screen class */
    .screen-full .value--xxlarge, .screen-half-vertical .value--xxlarge {{ font-size: 88px; }}
    .screen-full .value--large,   .screen-half-vertical .value--large   {{ font-size: 56px; }}
    .screen-full .value--small,   .screen-half-vertical .value--small   {{ font-size: 36px; }}
    .screen-half-horizontal .value--xxlarge {{ font-size: 72px; }}
    .screen-half-horizontal .value--large   {{ font-size: 48px; }}
    .screen-half-horizontal .value--small   {{ font-size: 32px; }}
    .screen-quadrant .value--xxlarge {{ font-size: 60px; }}
    .screen-quadrant .value--large   {{ font-size: 44px; }}
    .screen-quadrant .value--small   {{ font-size: 28px; }}

    .screen .label {{
      font-size: 13px;
      font-weight: 400;
      color: #555;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .screen-quadrant .label {{ font-size: 11px; }}

    .screen .w-full     {{ width: 100%; }}
    .screen .b-h-gray-5 {{ border-top: 1px solid #ccc; }}

    .screen .grid         {{ display: grid; }}
    .screen .grid--cols-2 {{ grid-template-columns: 1fr 1fr; }}

    /* Title bar */
    .screen .title_bar {{
      display: flex;
      align-items: center;
      gap: 8px;
      border-top: 1px solid #000;
      padding-top: 8px;
      margin-top: 8px;
      font-size: 12px;
      flex-shrink: 0;
    }}
    .screen-quadrant .title_bar {{ font-size: 10px; padding-top: 6px; margin-top: 6px; }}
    .screen .title_bar .image    {{ width: 18px; height: 18px; }}
    .screen .title_bar .title    {{ font-weight: 600; }}
    .screen .title_bar .instance {{ margin-left: auto; color: #666; }}
  </style>
</head>
<body>
  <div class="toolbar">
    <span>TRMNL Preview &mdash; all views</span>
    <a href="/">&#8635; Refresh</a>
  </div>

  <div class="view-section">
    <span class="view-label">Full &mdash; 800&times;480 &mdash; key: <code>markup</code></span>
    <div class="screen screen-full">{markup_full}</div>
  </div>

  <div class="view-section">
    <span class="view-label">Half-horizontal &mdash; 800&times;240 &mdash; key: <code>markup_half_horizontal</code></span>
    <div class="screen screen-half-horizontal">{markup_half_horizontal}</div>
  </div>

  <div class="view-section">
    <span class="view-label">Half-vertical &mdash; 400&times;480 &mdash; key: <code>markup_half_vertical</code></span>
    <div class="screen screen-half-vertical">{markup_half_vertical}</div>
  </div>

  <div class="view-section">
    <span class="view-label">Quadrant &mdash; 400&times;240 &mdash; key: <code>markup_quadrant</code></span>
    <div class="screen screen-quadrant">{markup_quadrant}</div>
  </div>
</body>
</html>
"""

ERROR_PAGE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>TRMNL Preview &mdash; Error</title>
  <style>
    body {{ font-family: monospace; padding: 2em; background: #fff4f4; }}
    pre  {{ background: #fff; border: 1px solid #ddd; padding: 1em; white-space: pre-wrap; }}
    a    {{ color: #333; }}
  </style>
</head>
<body>
  <h2>Failed to fetch sensor data</h2>
  <pre>{error}</pre>
  <p><a href="/">&#8635; Try again</a></p>
</body>
</html>
"""


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            query = parse_qs(urlparse(self.path).query)
            tz_name = query.get("tz", [lambda_function.DEFAULT_TZ])[0]
            tz = lambda_function.resolve_tz(tz_name)
            sensors = lambda_function.get_measurements()
            html = PAGE.format(
                markup_full=lambda_function.build_markup(lambda_function.MARKUP_FULL, sensors, tz),
                markup_half_horizontal=lambda_function.build_markup(lambda_function.MARKUP_HALF_HORIZONTAL, sensors, tz),
                markup_half_vertical=lambda_function.build_markup(lambda_function.MARKUP_HALF_VERTICAL, sensors, tz),
                markup_quadrant=lambda_function.build_markup(lambda_function.MARKUP_QUADRANT, sensors, tz),
            )
            self._respond(200, html)
        except Exception as e:
            self._respond(500, ERROR_PAGE.format(error=e))

    def _respond(self, status, html):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"  {fmt % args}")


if __name__ == "__main__":
    server = HTTPServer(("", PORT), PreviewHandler)
    print(f"Preview server running → http://localhost:{PORT}")
    print("All three view sizes are shown on a single page.")
    print("Each page load fetches fresh data from the Ruuvi API.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
