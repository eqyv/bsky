import unittest
from unittest.mock import Mock, patch

import requests

from adapters.xquik import XquikAdapter


class XquikAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = XquikAdapter("xq_test", "@example")

    @patch("adapters.xquik.requests.post")
    def test_posts_text_and_public_media_urls(self, post):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {"success": True, "tweetId": "123"}
        post.return_value = response

        result = self.adapter.post(
            "hello",
            media_paths=["/tmp/local.jpg"],
            media_urls=["https://example.com/public.jpg"],
        )

        self.assertEqual(
            result,
            {
                "success": True,
                "url": "https://x.com/i/web/status/123",
                "error": None,
            },
        )
        post.assert_called_once_with(
            "https://xquik.com/api/v1/x/tweets",
            headers={
                "Content-Type": "application/json",
                "X-API-Key": "xq_test",
            },
            json={
                "account": "@example",
                "text": "hello",
                "media": ["https://example.com/public.jpg"],
            },
            timeout=30,
        )
        response.raise_for_status.assert_called_once_with()

    @patch("adapters.xquik.requests.post")
    def test_treats_pending_confirmation_as_accepted(self, post):
        response = Mock()
        response.status_code = 202
        post.return_value = response

        result = self.adapter.post("hello")

        self.assertTrue(result["success"])
        self.assertIsNone(result["url"])
        self.assertIsNone(result["error"])
        response.json.assert_not_called()

    @patch("adapters.xquik.requests.post")
    def test_reports_request_failures(self, post):
        post.side_effect = requests.exceptions.Timeout("timed out")

        result = self.adapter.post("hello")

        self.assertFalse(result["success"])
        self.assertIsNone(result["url"])
        self.assertEqual(result["error"], "timed out")


if __name__ == "__main__":
    unittest.main()
