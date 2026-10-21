
import json
import os
import hmac

from http.server import BaseHTTPRequestHandler


WEBHOOK_SECRET = os.environ["JOURNAL_WEBHOOK_SECRET"]


class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        received_secret = self.headers.get(
            "X-Webhook-Secret", ""
        )

        if not hmac.compare_digest(
            received_secret, WEBHOOK_SECRET
        ):
            self.send_response(401)
            self.end_headers()
            return

        content_length = int(
            self.headers.get("Content-Length", "0")
        )

        if content_length <= 0 or content_length > 20000:
            self.send_response(400)
            self.end_headers()
            return

        try:
            body = json.loads(
                self.rfile.read(content_length)
            )

            if (
                body.get("type") != "INSERT"
                or body.get("table") != "journal_entries"
                or body.get("schema") != "public"
            ):
                self.send_response(400)
                self.end_headers()
                return

            record = body["record"]
            entry_id = record["id"]

            print(
                f"Journal webhook received for entry {entry_id}",
                flush=True
            )

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Webhook received")

        except (ValueError, KeyError, TypeError):
            self.send_response(400)
            self.end_headers()
