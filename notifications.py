"""notifications.py — Send FCM push notifications from the server."""
import os
import firebase_admin
from firebase_admin import credentials, messaging

_cred = credentials.Certificate(
    os.environ.get("FIREBASE_KEY", "firebase-service-account.json"))
firebase_admin.initialize_app(_cred)


def send_push(token: str, title: str, body: str, data: dict | None = None) -> bool:
    try:
        messaging.send(messaging.Message(
            token=token,
            data={k: str(v) for k, v in (data or {}).items()},
            notification=messaging.Notification(title=title, body=body),
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(channel_id="job_alerts"),
            ),
        ))
        return True
    except Exception as e:
        print(f"Push failed: {e}")
        return False


def send_to_many(tokens: list[str], title: str, body: str) -> list[str]:
    """Returns dead tokens for pruning."""
    dead = []
    for t in tokens:
        ok = send_push(t, title, body)
        if not ok:
            dead.append(t)
    return dead
