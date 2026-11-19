"""
Step 10 -- Gmail inbox integration. Lists candidate audit-request emails from
a real mailbox and extracts their text (body or PDF attachment) so they can
be fed into the same decompose() -> run_checks() -> pack() -> letter()
pipeline as the sample requests.

Single mailbox, single OAuth grant: the refresh token lives in
audit.oauth_tokens (one row, provider='gmail'). This app never sees or
stores your Google password -- only the token your own consent screen grants
it, scoped to gmail.readonly (list + read messages, never send or delete).

You never see your inbox's full contents through an LLM here either --
list_candidate_messages() only returns metadata (subject/from/date/snippet)
for the UI to show as a picklist; the LLM only sees the body of whichever
single message a human explicitly clicks "run" on.
"""
import base64
import email
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from . import db
from .config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI, GMAIL_SEARCH_QUERY

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _client_config():
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }


def is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)


def build_auth_url() -> str:
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=GOOGLE_REDIRECT_URI)
    url, _state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url


def exchange_code(code: str) -> None:
    """Called from the OAuth callback with Google's one-time code. Stores the
    refresh token -- this is the ONLY place a token is written from a fresh
    grant; every later use just refreshes it in place."""
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=GOOGLE_REDIRECT_URI)
    flow.fetch_token(code=code)
    creds = flow.credentials
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit.oauth_tokens (provider, refresh_token, access_token, expiry, scope, updated_at)
               VALUES ('gmail', %s, %s, %s, %s, now())
               ON CONFLICT (provider) DO UPDATE SET
                 refresh_token = EXCLUDED.refresh_token, access_token = EXCLUDED.access_token,
                 expiry = EXCLUDED.expiry, scope = EXCLUDED.scope, updated_at = now()""",
            (creds.refresh_token, creds.token, creds.expiry, " ".join(creds.scopes or SCOPES)),
        )
        conn.commit()


def is_connected() -> bool:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM audit.oauth_tokens WHERE provider = 'gmail'")
        return cur.fetchone() is not None


def _load_credentials() -> Credentials:
    with db.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT refresh_token, access_token, expiry, scope FROM audit.oauth_tokens WHERE provider = 'gmail'")
        row = cur.fetchone()
    if not row:
        raise RuntimeError("Gmail is not connected yet -- visit /api/inbox/auth-url first")

    creds = Credentials(
        token=row["access_token"],
        refresh_token=row["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=(row["scope"] or " ".join(SCOPES)).split(),
    )
    if not creds.valid:
        creds.refresh(Request())
        with db.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE audit.oauth_tokens SET access_token = %s, expiry = %s, updated_at = now() WHERE provider = 'gmail'",
                (creds.token, creds.expiry),
            )
            conn.commit()
    return creds


def _service():
    return build("gmail", "v1", credentials=_load_credentials(), cache_discovery=False)


def _find_part(payload, mime_type):
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        return payload["body"]["data"]
    for part in payload.get("parts", []) or []:
        found = _find_part(part, mime_type)
        if found:
            return found
    return None


def _find_pdf_attachment(payload):
    if payload.get("filename", "").lower().endswith(".pdf") and payload.get("body", {}).get("attachmentId"):
        return payload["filename"], payload["body"]["attachmentId"]
    for part in payload.get("parts", []) or []:
        found = _find_pdf_attachment(part)
        if found:
            return found
    return None


def list_candidate_messages(max_results: int = 20) -> list[dict]:
    svc = _service()
    resp = svc.users().messages().list(userId="me", q=GMAIL_SEARCH_QUERY, maxResults=max_results).execute()
    out = []
    for m in resp.get("messages", []):
        msg = svc.users().messages().get(userId="me", id=m["id"], format="metadata",
                                         metadataHeaders=["Subject", "From", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        has_pdf = _find_pdf_attachment(msg["payload"]) is not None
        out.append({
            "message_id": m["id"],
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "snippet": msg.get("snippet", ""),
            "has_pdf": has_pdf,
        })
    return out


def get_message_text(message_id: str) -> str:
    """Prefers a PDF attachment's extracted text (matches how REQ-02 is
    handled today); falls back to the plain-text body."""
    svc = _service()
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = msg["payload"]

    pdf = _find_pdf_attachment(payload)
    if pdf:
        filename, attachment_id = pdf
        att = svc.users().messages().attachments().get(userId="me", messageId=message_id, id=attachment_id).execute()
        pdf_bytes = base64.urlsafe_b64decode(att["data"])
        import io
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf_doc:
            return "\n".join(p.extract_text() or "" for p in pdf_doc.pages)

    data = _find_part(payload, "text/plain")
    if data:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    html = _find_part(payload, "text/html")
    if html:
        raw = base64.urlsafe_b64decode(html).decode("utf-8", errors="replace")
        return email.message_from_string(raw).get_payload() if raw else ""

    raise ValueError(f"message {message_id} has neither a PDF attachment nor a text body")
