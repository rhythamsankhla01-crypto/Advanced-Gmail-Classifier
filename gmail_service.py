import base64
import os
import re
from email.utils import parseaddr

import joblib
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from category_classifier import classify_category

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "spam_model.joblib")

class GmailAnalyzer:
    def __init__(self, access_token, refresh_token, token_uri, client_id, client_secret):
        self.credentials = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=client_id,
            client_secret=client_secret,
        )
        self.service = build("gmail", "v1", credentials=self.credentials)
        self.model = joblib.load(MODEL_PATH)

    @staticmethod
    def header(headers, name):
        for h in headers:
            if h.get("name", "").lower() == name.lower():
                return h.get("value", "")
        return ""

    @staticmethod
    def decode_part(data):
        if not data:
            return ""
        try:
            return base64.urlsafe_b64decode(data.encode("utf-8")).decode(
                "utf-8", errors="ignore"
            )
        except Exception:
            return ""

    def extract_text(self, payload):
        mime = payload.get("mimeType", "")
        if mime == "text/plain":
            return self.decode_part(payload.get("body", {}).get("data"))

        parts = payload.get("parts", [])
        text = []

        for part in parts:
            part_mime = part.get("mimeType", "")
            if part_mime == "text/plain":
                text.append(self.decode_part(part.get("body", {}).get("data")))
            elif part.get("parts"):
                text.append(self.extract_text(part))

        return "\n".join(x for x in text if x).strip()

    def fetch_messages(self, limit=25):
        response = self.service.users().messages().list(
            userId="me",
            maxResults=limit,
            labelIds=["INBOX"],
        ).execute()

        result = []
        for item in response.get("messages", []):
            msg = self.service.users().messages().get(
                userId="me",
                id=item["id"],
                format="full",
            ).execute()

            payload = msg.get("payload", {})
            headers = payload.get("headers", [])
            sender_raw = self.header(headers, "From")
            sender_name, sender_email = parseaddr(sender_raw)
            subject = self.header(headers, "Subject") or "(No subject)"
            body = self.extract_text(payload)

            result.append({
                "id": item["id"],
                "sender": sender_name or sender_email or sender_raw,
                "sender_email": sender_email,
                "subject": subject,
                "body": body,
                "snippet": msg.get("snippet", ""),
                "date": self.header(headers, "Date"),
            })
        return result

    def fetch_and_classify(self, limit=25):
        messages = self.fetch_messages(limit)
        output = []

        for msg in messages:
            text = f"{msg['subject']}\n{msg['sender']}\n{msg['body'][:8000]}"
            probabilities = self.model.predict_proba([text])[0]
            prediction = int(self.model.predict([text])[0])
            spam_probability = float(probabilities[1]) if len(probabilities) > 1 else float(prediction)

            output.append({
                "id": msg["id"],
                "sender": msg["sender"],
                "sender_email": msg["sender_email"],
                "subject": msg["subject"],
                "snippet": msg["snippet"],
                "body": msg["body"][:12000],
                "date": msg["date"],
                "spam": bool(prediction),
                "spam_probability": round(spam_probability * 100, 1),
                "confidence": round(max(probabilities) * 100, 1),
                "category": classify_category(msg["subject"], msg["sender"], msg["body"]),
            })

        return output
