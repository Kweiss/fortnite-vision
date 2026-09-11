"""Optional, user-configured delivery for matched alerts."""

from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection
import json
from queue import Queue
import threading
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import keyring
from keyring.errors import PasswordDeleteError


_TELEGRAM_KEYRING_SERVICE = "FortniteVision"
_TELEGRAM_KEYRING_ACCOUNT = "telegram_bot_token"
_TELEGRAM_HOST = "api.telegram.org"
_TELEGRAM_REQUEST_TIMEOUT_SECONDS = 8.0
_TELEGRAM_CONNECTION_IDLE_SECONDS = 60.0


@dataclass(frozen=True)
class TelegramDeliveryResult:
    """Outcome metadata for one alert sent by the background dispatcher."""

    title: str
    queue_seconds: float
    request_seconds: float
    error: str | None = None


@dataclass(frozen=True)
class _TelegramAlert:
    bot_token: str
    chat_id: str
    title: str
    message: str
    queued_at: float


class TelegramAlertDispatcher:
    """Serialize alert delivery and reuse Telegram's HTTPS connection when possible."""

    def __init__(
        self,
        on_result: Callable[[TelegramDeliveryResult], None],
        request_timeout_seconds: float = _TELEGRAM_REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._on_result = on_result
        self._request_timeout_seconds = request_timeout_seconds
        self._alerts: Queue[_TelegramAlert | None] = Queue()
        self._connection: HTTPSConnection | None = None
        self._connection_last_used_at: float | None = None
        self._thread = threading.Thread(
            target=self._run,
            name="Telegram alert delivery",
            daemon=True,
        )
        self._thread.start()

    def enqueue(self, bot_token: str, chat_id: str, title: str, message: str) -> None:
        """Queue an alert immediately; network work stays off the UI thread."""

        token = bot_token.strip()
        destination = chat_id.strip()
        if not token:
            raise ValueError("Enter a Telegram bot token.")
        if not destination:
            raise ValueError("Enter a Telegram chat ID.")
        self._alerts.put(
            _TelegramAlert(
                bot_token=token,
                chat_id=destination,
                title=title,
                message=message,
                queued_at=time.perf_counter(),
            )
        )

    def close(self) -> None:
        """Stop accepting work when the application exits without blocking shutdown."""

        self._alerts.put(None)
        self._thread.join(timeout=0.5)
        self._close_connection()

    def _run(self) -> None:
        while True:
            alert = self._alerts.get()
            if alert is None:
                return

            started_at = time.perf_counter()
            error: str | None = None
            try:
                self._send(alert)
            except Exception as exc:
                error = str(exc)
                self._close_connection()

            self._on_result(
                TelegramDeliveryResult(
                    title=alert.title,
                    queue_seconds=started_at - alert.queued_at,
                    request_seconds=time.perf_counter() - started_at,
                    error=error,
                )
            )

    def _send(self, alert: _TelegramAlert) -> None:
        if self._connection_has_been_idle_too_long():
            self._close_connection()

        connection = self._connection
        if connection is None:
            connection = HTTPSConnection(
                _TELEGRAM_HOST,
                timeout=self._request_timeout_seconds,
            )
            self._connection = connection

        encoded_token = quote(alert.bot_token, safe=":")
        payload = urlencode(
            {
                "chat_id": alert.chat_id,
                "text": f"{alert.title}\n{alert.message}",
                "disable_web_page_preview": "true",
            }
        ).encode("utf-8")
        try:
            connection.request(
                "POST",
                f"/bot{encoded_token}/sendMessage",
                body=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response = connection.getresponse()
            raw_body = response.read()
        except (HTTPException, OSError, TimeoutError) as exc:
            raise RuntimeError(f"Telegram connection failed: {exc}") from exc

        if response.status >= 400:
            raise RuntimeError(f"Telegram returned HTTP {response.status}.")

        try:
            body = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Telegram returned an unreadable response.") from exc
        _validate_telegram_response(body)

        if response.will_close:
            self._close_connection()
        else:
            self._connection_last_used_at = time.perf_counter()

    def _connection_has_been_idle_too_long(self) -> bool:
        if self._connection is None or self._connection_last_used_at is None:
            return False
        return time.perf_counter() - self._connection_last_used_at >= _TELEGRAM_CONNECTION_IDLE_SECONDS

    def _close_connection(self) -> None:
        connection, self._connection = self._connection, None
        self._connection_last_used_at = None
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def save_telegram_bot_token(bot_token: str) -> None:
    """Store the bot token in the user's Windows Credential Manager."""

    token = bot_token.strip()
    if not token:
        raise ValueError("Enter a Telegram bot token.")
    keyring.set_password(_TELEGRAM_KEYRING_SERVICE, _TELEGRAM_KEYRING_ACCOUNT, token)


def get_telegram_bot_token() -> str:
    """Return the locally stored bot token without exposing it in settings."""

    token = keyring.get_password(_TELEGRAM_KEYRING_SERVICE, _TELEGRAM_KEYRING_ACCOUNT)
    if not token:
        raise ValueError("No Telegram bot token is stored. Enter one before sending alerts.")
    return token


def clear_telegram_bot_token() -> None:
    """Remove the locally stored Telegram token when the user requests it."""

    try:
        keyring.delete_password(_TELEGRAM_KEYRING_SERVICE, _TELEGRAM_KEYRING_ACCOUNT)
    except PasswordDeleteError:
        pass


def send_telegram(bot_token: str, chat_id: str, title: str, message: str) -> None:
    """Send a plain-text alert through Telegram's official Bot API."""

    destination = chat_id.strip()
    if not destination:
        raise ValueError("Enter a Telegram chat ID.")
    _telegram_request(
        bot_token,
        "sendMessage",
        {
            "chat_id": destination,
            "text": f"{title}\n{message}",
            "disable_web_page_preview": "true",
        },
    )


def find_recent_telegram_chat_id(bot_token: str) -> str:
    """Return the most recent private, group, or channel chat seen by the bot."""

    response = _telegram_request(
        bot_token,
        "getUpdates",
        {"limit": "100", "allowed_updates": json.dumps(["message", "channel_post"])},
    )
    for update in reversed(response.get("result", [])):
        if not isinstance(update, dict):
            continue
        for update_type in ("message", "channel_post"):
            message = update.get(update_type)
            if isinstance(message, dict) and isinstance(message.get("chat"), dict):
                chat_id = message["chat"].get("id")
                if chat_id is not None:
                    return str(chat_id)
    raise ValueError("No recent Telegram chat was found. Send the bot /start, then try again.")


def _telegram_request(bot_token: str, method: str, payload: dict[str, str]) -> dict[str, object]:
    token = bot_token.strip()
    if not token:
        raise ValueError("Enter a Telegram bot token.")
    request = Request(
        f"https://{_TELEGRAM_HOST}/bot{quote(token, safe=':')}/{method}",
        data=urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=_TELEGRAM_REQUEST_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Telegram returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError(f"Telegram connection failed: {exc.reason}") from exc

    _validate_telegram_response(body)
    return body


def _validate_telegram_response(body: object) -> None:
    if not isinstance(body, dict) or not body.get("ok"):
        description = (
            body.get("description", "Telegram rejected the request.")
            if isinstance(body, dict)
            else "Telegram rejected the request."
        )
        raise RuntimeError(str(description))
