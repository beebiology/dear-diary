
import json
import os
import hmac

from http.server import BaseHTTPRequestHandler
from urllib.request import Request, urlopen

from supabase import create_client


WEBHOOK_SECRET = os.environ["JOURNAL_WEBHOOK_SECRET"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]
EMAIL_FROM = os.environ["EMAIL_FROM"]

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"]   
)


def send_journal_email(entry_id):
    # Retrieve the original entry from Supabase (CODE ADDED: THE LINE JUST UNDER THIS)
    print("Step 1: Retrieving journal entry", flush=True) 

    
print("Step 1: Retrieving journal entry", flush=True)

request = Request(
    f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/journal_entries",
    headers={
        "apikey": os.environ["SUPABASE_SECRET_KEY"],
        "Authorization": f"Bearer {os.environ['SUPABASE_SECRET_KEY']}",
        "Accept": "application/json"
    }
)

# Add the entry ID as a query parameter
from urllib.parse import urlencode

request.full_url += "?" + urlencode({
    "id": f"eq.{entry_id}",
    "select": "id,user_id,entry_text,entry_date"
})

with urlopen(request, timeout=10) as response:
    records = json.load(response)

if len(records) != 1:
    raise ValueError("Journal entry not found")

entry = records[0]

print("Step 1 complete: Journal entry retrieved", flush=True)


    # Look up the owner's email address (CODE ADDED)
    print("Step 2: Retrieving user email", flush=True)

    user_result = supabase.auth.admin.get_user_by_id(
        entry["user_id"]
    )

    email = user_result.user.email

    if not email:
        raise ValueError("Journal owner has no email")

    # Prepare the outgoing email
    email_data = {
        "from": EMAIL_FROM,
        "to": [email],
        "subject": f"Your Dear Diary entry - {entry['entry_date']}",
        "text": (
            f"Your journal entry from {entry['entry_date']}:\n\n"
            f"{entry['entry_text']}"
        )
    }

    # Send the email using Resend
    request = Request(
        "https://api.resend.com/emails",
        data=json.dumps(email_data).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"journal-entry-{entry_id}"
        },
        method="POST"
    )

    print("Step 3: Sending email through Resend", flush=True)

    with urlopen(request, timeout=15) as response:
        return json.load(response)


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

        try:
            content_length = int(
                self.headers.get("Content-Length", "0")
            )

            if content_length <= 0 or content_length > 20000:
                self.send_response(400)
                self.end_headers()
                return

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

            entry_id = body["record"]["id"]

            result = send_journal_email(entry_id)

            print(
                f"Email accepted for entry {entry_id}: "
                f"{result.get('id')}",
                flush=True
            )

            self.send_response(200)
            self.end_headers()

        except (ValueError, KeyError, TypeError):
            self.send_response(400)
            self.end_headers()

        except Exception as error:
            print(
                f"Email webhook error: "
                f"{type(error).__name__}: {error}",
                flush=True
            )

            self.send_response(500)
            self.end_headers()
