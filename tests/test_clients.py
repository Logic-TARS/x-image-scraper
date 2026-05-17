import importlib
import sys
import types
import unittest
from unittest import mock


class FakeResponse:
    def __init__(self, text="", json_data=None, error=None):
        self.text = text
        self._json_data = json_data
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self._json_data


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.headers = {}
        self.proxies = {}
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


class TestNoAPIClient(unittest.TestCase):
    def import_clients_with_session(self, session):
        fake_requests = types.SimpleNamespace(
            RequestException=RuntimeError,
            Session=lambda: session,
        )
        sys.modules.pop("xscrape.clients", None)
        with mock.patch.dict(sys.modules, {"requests": fake_requests}):
            return importlib.import_module("xscrape.clients")

    def test_normalizes_encoded_nitter_pic_urls_and_deduplicates(self):
        html = (
            '<a href="/pic/media%2Fabc.jpg%3Fname%3Dsmall"></a>'
            '<a href="/pic/media%2Fabc.jpg%3Fname%3Dsmall"></a>'
            '<source src="/video/1.mp4">'
        )
        session = FakeSession([FakeResponse(html)])
        clients = self.import_clients_with_session(session)

        client = clients.NoAPIClient("https://nitter.example")
        images = client.get_images_from_profile("user", pages=1)

        self.assertEqual(
            images,
            [
                {"url": "https://pbs.twimg.com/media/abc.jpg?name=small", "type": "photo", "tweet_id": ""},
                {"url": "https://nitter.example/video/1.mp4", "type": "video", "tweet_id": ""},
            ],
        )

    def test_falls_back_to_next_default_instance(self):
        session = FakeSession(
            [
                FakeResponse(error=RuntimeError("down")),
                FakeResponse('<a href="/pic/media%2Ffallback.jpg"></a>'),
            ]
        )
        clients = self.import_clients_with_session(session)
        clients.NoAPIClient.DEFAULT_INSTANCES = ["https://bad.example", "https://good.example"]

        client = clients.NoAPIClient()
        with mock.patch.object(clients.log, "warning"):
            images = client.get_images_from_profile("user", pages=1)

        self.assertEqual(client.instance, "https://good.example")
        self.assertEqual(images[0]["url"], "https://pbs.twimg.com/media/fallback.jpg")
        self.assertEqual(session.calls[0][0], "https://bad.example/user/media")
        self.assertEqual(session.calls[1][0], "https://good.example/user/media")


class TestTwitterAPIClient(unittest.TestCase):
    def import_clients_with_session(self, session):
        fake_requests = types.SimpleNamespace(
            RequestException=RuntimeError,
            Session=lambda: session,
        )
        sys.modules.pop("xscrape.clients", None)
        with mock.patch.dict(sys.modules, {"requests": fake_requests}):
            return importlib.import_module("xscrape.clients")

    def test_search_recent_tweets_requests_metrics_media_and_users(self):
        session = FakeSession([FakeResponse(json_data={"data": [], "meta": {}})])
        clients = self.import_clients_with_session(session)

        client = clients.TwitterAPIClient("token")
        data = client.search_recent_tweets("blue archive has:images", max_results=500, next_token="next")

        self.assertEqual(data, {"data": [], "meta": {}})
        self.assertEqual(session.calls[0][0], "https://api.x.com/2/tweets/search/recent")
        params = session.calls[0][1]["params"]
        self.assertEqual(params["max_results"], 100)
        self.assertEqual(params["next_token"], "next")
        self.assertIn("public_metrics", params["tweet.fields"])
        self.assertIn("attachments.media_keys", params["expansions"])
        self.assertIn("author_id", params["expansions"])
        self.assertIn("url", params["media.fields"])

    def test_extract_image_urls_includes_metrics_and_author(self):
        session = FakeSession([])
        clients = self.import_clients_with_session(session)
        client = clients.TwitterAPIClient("token")

        images = client.extract_image_urls(
            {
                "data": [
                    {
                        "id": "1",
                        "author_id": "u1",
                        "created_at": "2026-05-16T00:00:00Z",
                        "text": "Blue Archive",
                        "public_metrics": {"like_count": 123, "retweet_count": 4, "reply_count": 5, "quote_count": 6},
                        "attachments": {"media_keys": ["m1"]},
                    }
                ],
                "includes": {
                    "users": [{"id": "u1", "username": "artist", "name": "Artist"}],
                    "media": [{"media_key": "m1", "type": "photo", "url": "https://pbs.twimg.com/media/a.jpg"}],
                },
            }
        )

        self.assertEqual(images[0]["like_count"], 123)
        self.assertEqual(images[0]["author_username"], "artist")
        self.assertEqual(images[0]["url"], "https://pbs.twimg.com/media/a.jpg?format=jpg&name=orig")


if __name__ == "__main__":
    unittest.main()
