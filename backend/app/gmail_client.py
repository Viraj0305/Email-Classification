from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
SCOPES = [GMAIL_READONLY_SCOPE]

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
DEFAULT_CREDENTIALS_FILE = BACKEND_DIR / "credentials.json"
DEFAULT_TOKEN_FILE = BACKEND_DIR / ".gmail-token.json"


class GmailConfigurationError(RuntimeError):
    pass


def get_credentials_file_path() -> Path:
    configured_path = os.getenv("GMAIL_OAUTH_CREDENTIALS_FILE")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return DEFAULT_CREDENTIALS_FILE


def get_token_file_path() -> Path:
    configured_path = os.getenv("GMAIL_OAUTH_TOKEN_FILE")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return DEFAULT_TOKEN_FILE


def get_connection_status() -> dict[str, Any]:
    credentials_file = get_credentials_file_path()
    token_file = get_token_file_path()
    return {
        "connected": token_file.exists(),
        "credentials_file_configured": credentials_file.exists(),
        "credentials_file_path": str(credentials_file),
        "token_file_path": str(token_file),
        "scope": GMAIL_READONLY_SCOPE,
    }


def build_gmail_service():
    credentials_file = get_credentials_file_path()
    token_file = get_token_file_path()
    creds = None

    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_file.exists():
                raise GmailConfigurationError(
                    "Gmail OAuth credentials file not found. Download your Google OAuth desktop app "
                    "credentials JSON and save it as backend/credentials.json, or set "
                    "GMAIL_OAUTH_CREDENTIALS_FILE."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file),
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("gmail", "v1", credentials=creds)


def fetch_message_batch(max_results: int = 25, query: str = "") -> list[dict[str, Any]]:
    gmail = build_gmail_service()

    response = (
        gmail.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query or None)
        .execute()
    )
    messages = response.get("messages", [])

    detailed_messages: list[dict[str, Any]] = []
    for item in messages:
        raw_message = (
            gmail.users()
            .messages()
            .get(userId="me", id=item["id"], format="full")
            .execute()
        )
        detailed_messages.append(_normalize_message(raw_message))

    return detailed_messages


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("payload", {})
    headers = _headers_to_dict(payload.get("headers", []))
    body_text = _extract_message_body(payload).strip()

    return {
        "message_id": message.get("id", ""),
        "thread_id": message.get("threadId", ""),
        "sender": headers.get("From", ""),
        "subject": headers.get("Subject", "(no subject)"),
        "received_at": headers.get("Date", ""),
        "snippet": (message.get("snippet") or body_text[:180]).strip(),
        "body": body_text or message.get("snippet", ""),
    }


def _headers_to_dict(headers: list[dict[str, str]]) -> dict[str, str]:
    return {header.get("name", ""): header.get("value", "") for header in headers}


def _extract_message_body(payload: dict[str, Any]) -> str:
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")
    parts = payload.get("parts", [])

    if body_data and mime_type == "text/plain":
        return _decode_base64_text(body_data)

    for part in parts:
        text = _extract_message_body(part)
        if text:
            if part.get("mimeType") == "text/plain":
                return text
            if mime_type == "multipart/alternative":
                return text

    if body_data and mime_type == "text/html":
        return _strip_html(_decode_base64_text(body_data))

    if body_data:
        return _decode_base64_text(body_data)

    return ""


def _decode_base64_text(data: str) -> str:
    padding = "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(data + padding)
    return decoded.decode("utf-8", errors="ignore")


def _strip_html(value: str) -> str:
    collapsed = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", collapsed).strip()
