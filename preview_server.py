#!/usr/bin/env python3
"""
Local preview server for the TRMNL markup.

Fetches live sensor data from the Ruuvi API on each request and renders
the markup inside a browser page styled to approximate the TRMNL e-ink
display (800×480). Reload the page to refresh the data.

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

# Load credentials before importing lambda_function, which reads them at
# module load time.
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
    /* --- Page chrome -------------------------------------------------- */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #c8c8c8;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 16px;
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }}

    .toolbar {{
      color: #444;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .toolbar a {{
      color: #222;
      text-decoration: none;
      border: 1px solid #888;
      border-radius: 4px;
      padding: 3px 10px;
      background: #eee;
    }}
    .toolbar a:hover {{ background: #ddd; }}

    /* Simulated e-ink screen */
    .screen {{
      width: 800px;
      height: 480px;
      background: #fff;
      border: 2px solid #555;
      border-radius: 4px;
      box-shadow: 0 6px 24px rgba(0,0,0,0.3);
      overflow: hidden;
      display: flex;
      flex-direction: column;
      padding: 20px 20px 12px;
      color: #000;
    }}

    /* --- TRMNL CSS approximation -------------------------------------- */

    .screen .layout {{
      display: flex;
      flex: 1;
      min-height: 0;
    }}
    .screen .layout--col   {{ flex-direction: column; }}
    .screen .gap--space-between {{ justify-content: space-between; }}

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
    .screen .value--xxlarge {{ font-size: 96px; }}
    .screen .value--large   {{ font-size: 64px; }}
    .screen .value--small   {{ font-size: 44px; }}

    .screen .label {{
      font-size: 14px;
      font-weight: 400;
      color: #444;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}

    .screen .w-full        {{ width: 100%; }}
    .screen .b-h-gray-5    {{ border-top: 1px solid #bbb; }}

    .screen .grid           {{ display: grid; }}
    .screen .grid--cols-2   {{ grid-template-columns: 1fr 1fr; }}

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
    .screen .title_bar .image {{
      width: 20px;
      height: 20px;
    }}
    .screen .title_bar .title    {{ font-weight: 600; }}
    .screen .title_bar .instance {{ margin-left: auto; color: #555; }}
  </style>
</head>
<body>
  <div class="toolbar">
    <span>TRMNL preview &mdash; 800&times;480</span>
    <a href="/">&#8635; Refresh</a>
  </div>
  <div class="screen">
    {markup}
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
            sensors = lambda_function.get_measurements()
            markup = lambda_function.build_markup(sensors)
            self._respond(200, PAGE.format(markup=markup))
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
    print("Each page load fetches fresh data from the Ruuvi API.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
