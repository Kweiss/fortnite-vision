import json
import threading
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

from droid_monitor.notifications import (
    TelegramAlertDispatcher,
    find_recent_telegram_chat_id,
    send_telegram,
)


class _Response:
    status = 200

    def __init__(self, body: dict[str, object]) -> None:
        self._body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._body).encode("utf-8")


class _PersistentResponse:
    status = 200
    will_close = False

    def read(self) -> bytes:
        return b'{"ok": true, "result": {}}'


class TelegramNotificationTests(unittest.TestCase):
    @patch("droid_monitor.notifications.urlopen")
    def test_sends_a_plain_text_telegram_alert(self, mocked_urlopen: object) -> None:
        mocked_urlopen.return_value = _Response({"ok": True, "result": {}})  # type: ignore[attr-defined]

        send_telegram("123:secret", "-100123", "Droid alert", "Rainbow Droid (Epic)")

        request = mocked_urlopen.call_args.args[0]  # type: ignore[attr-defined]
        self.assertEqual(request.full_url, "https://api.telegram.org/bot123:secret/sendMessage")
        self.assertEqual(
            parse_qs(request.data.decode("utf-8")),
            {
                "chat_id": ["-100123"],
                "text": ["Droid alert\nRainbow Droid (Epic)"],
                "disable_web_page_preview": ["true"],
            },
        )

    @patch("droid_monitor.notifications.urlopen")
    def test_finds_the_most_recent_telegram_chat(self, mocked_urlopen: object) -> None:
        mocked_urlopen.return_value = _Response(
            {
                "ok": True,
                "result": [
                    {"update_id": 1, "message": {"chat": {"id": 111}}},
                    {"update_id": 2, "message": {"chat": {"id": -100222}}},
                ],
            }
        )  # type: ignore[attr-defined]

        self.assertEqual(find_recent_telegram_chat_id("123:secret"), "-100222")

    @patch("droid_monitor.notifications.HTTPSConnection")
    def test_alert_dispatcher_reuses_a_healthy_connection(self, mocked_connection: object) -> None:
        connection = Mock()
        connection.getresponse.side_effect = [_PersistentResponse(), _PersistentResponse()]
        mocked_connection.return_value = connection  # type: ignore[attr-defined]
        results: list[object] = []
        delivered = threading.Event()

        def on_result(result: object) -> None:
            results.append(result)
            if len(results) == 2:
                delivered.set()

        dispatcher = TelegramAlertDispatcher(on_result)
        try:
            dispatcher.enqueue("123:secret", "456", "First", "one")
            dispatcher.enqueue("123:secret", "456", "Second", "two")

            self.assertTrue(delivered.wait(1.0))
        finally:
            dispatcher.close()

        self.assertEqual(mocked_connection.call_count, 1)  # type: ignore[attr-defined]
        self.assertEqual(connection.request.call_count, 2)
        self.assertTrue(all(result.error is None for result in results))  # type: ignore[union-attr]

    @patch("droid_monitor.notifications.HTTPSConnection")
    def test_alert_dispatcher_replaces_an_idle_connection(self, mocked_connection: object) -> None:
        first_connection = Mock()
        first_connection.getresponse.return_value = _PersistentResponse()
        second_connection = Mock()
        second_connection.getresponse.return_value = _PersistentResponse()
        mocked_connection.side_effect = [first_connection, second_connection]  # type: ignore[attr-defined]
        first_delivered = threading.Event()
        second_delivered = threading.Event()
        results: list[object] = []

        def on_result(result: object) -> None:
            results.append(result)
            (first_delivered if len(results) == 1 else second_delivered).set()

        dispatcher = TelegramAlertDispatcher(on_result)
        try:
            dispatcher.enqueue("123:secret", "456", "First", "one")
            self.assertTrue(first_delivered.wait(1.0))
            dispatcher._connection_last_used_at = time.perf_counter() - 61.0

            dispatcher.enqueue("123:secret", "456", "Second", "two")
            self.assertTrue(second_delivered.wait(1.0))
        finally:
            dispatcher.close()

        self.assertEqual(mocked_connection.call_count, 2)  # type: ignore[attr-defined]
        self.assertTrue(first_connection.close.called)
        self.assertTrue(all(result.error is None for result in results))  # type: ignore[union-attr]
