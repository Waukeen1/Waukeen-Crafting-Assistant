import json
import unittest

from phone_notifications import (
    generate_ntfy_topic,
    normalize_ntfy_server,
    ntfy_subscription_url,
    publish_ntfy,
)


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class PhoneNotificationTests(unittest.TestCase):
    def test_generated_topic_is_long_and_url_safe(self):
        topic = generate_ntfy_topic()
        self.assertTrue(topic.startswith("wca-"))
        self.assertGreaterEqual(len(topic), 24)
        self.assertNotIn("/", topic)

    def test_server_and_subscription_url_are_normalized(self):
        self.assertEqual(normalize_ntfy_server("ntfy.sh/"), "https://ntfy.sh")
        self.assertEqual(
            ntfy_subscription_url("https://ntfy.sh/", "wca-test"),
            "https://ntfy.sh/wca-test",
        )

    def test_publish_uses_json_root_endpoint(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return _Response()

        publish_ntfy(
            "https://ntfy.sh/topic-must-not-be-in-url",
            "wca-test",
            "Craft stopped",
            "Target reached",
            priority=9,
            opener=opener,
        )
        self.assertEqual(captured["url"], "https://ntfy.sh/topic-must-not-be-in-url/")
        self.assertEqual(captured["payload"]["topic"], "wca-test")
        self.assertEqual(captured["payload"]["priority"], 5)
        self.assertEqual(captured["timeout"], 6.0)


if __name__ == "__main__":
    unittest.main()
