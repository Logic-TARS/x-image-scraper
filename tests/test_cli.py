import argparse
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from xscrape import cli


def make_args(**overrides):
    defaults = {
        "output": "",
        "workers": 1,
        "batch": None,
        "bearer_token": None,
        "nitter": "https://nitter.example",
        "pages": 2,
        "count": 200,
        "proxy": None,
        "since": None,
        "until": None,
        "keyword": None,
        "search_query": None,
        "search_name": None,
        "top": 10,
        "download_order": "time",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


class TestCliProcessUser(unittest.TestCase):
    def test_parser_accepts_username_as_first_positional(self):
        args = cli.build_parser().parse_args(
            ["testuser", "--nitter", "http://127.0.0.1:8765", "--pages", "1"]
        )

        self.assertEqual(args.username, "testuser")
        self.assertEqual(args.nitter, "http://127.0.0.1:8765")
        self.assertEqual(args.pages, 1)

    def test_parser_keeps_special_command_aliases_as_username(self):
        args = cli.build_parser().parse_args(["interactive"])

        self.assertEqual(args.username, "interactive")

    def test_process_user_uses_nitter_without_bearer_token(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = make_args(output=tmpdir)
            image = {"url": "https://example.com/image.jpg", "tweet_id": "1", "type": "photo"}
            no_api_client = mock.Mock()
            twitter_client = mock.Mock()
            downloader = mock.Mock()
            fake_modules = {
                "requests": types.SimpleNamespace(HTTPError=Exception),
                "xscrape.clients": types.SimpleNamespace(
                    NoAPIClient=no_api_client,
                    TwitterAPIClient=twitter_client,
                ),
                "xscrape.downloader": types.SimpleNamespace(ImageDownloader=downloader),
            }

            with mock.patch.dict(sys.modules, fake_modules):
                no_api_client.return_value.get_images_from_profile.return_value = [image]
                downloader.return_value.download_all.return_value = {"downloaded": 1, "skipped": 0, "failed": 0}

                result = cli.process_user("user", args)

            self.assertEqual(result, 0)
            no_api_client.assert_called_once_with(args.nitter, proxy=None)
            no_api_client.return_value.get_images_from_profile.assert_called_once_with("user", pages=2)
            twitter_client.assert_not_called()
            downloader.return_value.download_all.assert_called_once_with([image])
            self.assertTrue((Path(tmpdir) / "user" / "metadata.json").exists())

    def test_process_user_uses_api_with_bearer_token(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = make_args(output=tmpdir, bearer_token="token", count=50, keyword="cat")
            api_response = {"data": [], "meta": {}}
            image = {"url": "https://example.com/image.jpg", "tweet_id": "1", "type": "photo"}
            no_api_client = mock.Mock()
            twitter_client = mock.Mock()
            downloader = mock.Mock()
            fake_modules = {
                "requests": types.SimpleNamespace(HTTPError=Exception),
                "xscrape.clients": types.SimpleNamespace(
                    NoAPIClient=no_api_client,
                    TwitterAPIClient=twitter_client,
                ),
                "xscrape.downloader": types.SimpleNamespace(ImageDownloader=downloader),
            }

            with mock.patch.dict(sys.modules, fake_modules):
                twitter_client.return_value.get_user_id.return_value = "123"
                twitter_client.return_value.get_user_tweets.return_value = api_response
                twitter_client.return_value.extract_image_urls.return_value = [image]
                downloader.return_value.download_all.return_value = {"downloaded": 1, "skipped": 0, "failed": 0}

                result = cli.process_user("user", args)

            self.assertEqual(result, 0)
            twitter_client.assert_called_once_with("token", proxy=None)
            twitter_client.return_value.get_user_tweets.assert_called_once_with(
                "123",
                50,
                None,
                since=None,
                until=None,
            )
            twitter_client.return_value.extract_image_urls.assert_called_once_with(api_response, keyword="cat")
            no_api_client.assert_not_called()
            downloader.return_value.download_all.assert_called_once_with([image])

    def test_select_search_results_takes_top_likes_then_orders_by_time(self):
        images = [
            {"tweet_id": "old_high", "like_count": 100, "created_at": "2026-05-01T00:00:00Z"},
            {"tweet_id": "new_low", "like_count": 1, "created_at": "2026-05-16T00:00:00Z"},
            {"tweet_id": "new_high", "like_count": 90, "created_at": "2026-05-15T00:00:00Z"},
        ]

        selected = cli.select_search_results(images, top=2, download_order="time")

        self.assertEqual([item["tweet_id"] for item in selected], ["new_high", "old_high"])

    def test_process_search_uses_recent_search_and_downloads_selected_items(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            args = make_args(
                output=tmpdir,
                bearer_token="token",
                count=50,
                search_query="Blue Archive has:images",
                search_name="ba",
                top=1,
                download_order="likes",
            )
            api_response = {"data": [], "meta": {}}
            images = [
                {"url": "https://example.com/low.jpg", "tweet_id": "1", "type": "photo", "like_count": 10, "created_at": "2026-05-16T00:00:00Z"},
                {"url": "https://example.com/high.jpg", "tweet_id": "2", "type": "photo", "like_count": 50, "created_at": "2026-05-15T00:00:00Z"},
            ]
            twitter_client = mock.Mock()
            downloader = mock.Mock()
            fake_modules = {
                "requests": types.SimpleNamespace(HTTPError=Exception),
                "xscrape.clients": types.SimpleNamespace(TwitterAPIClient=twitter_client),
                "xscrape.downloader": types.SimpleNamespace(ImageDownloader=downloader),
            }

            with mock.patch.dict(sys.modules, fake_modules):
                twitter_client.return_value.search_recent_tweets.return_value = api_response
                twitter_client.return_value.extract_image_urls.return_value = images
                downloader.return_value.download_all.return_value = {"downloaded": 1, "skipped": 0, "failed": 0}

                result = cli.process_search(args)

            self.assertEqual(result, 0)
            twitter_client.assert_called_once_with("token", proxy=None)
            twitter_client.return_value.search_recent_tweets.assert_called_once_with(
                "Blue Archive has:images",
                50,
                None,
                since=None,
                until=None,
            )
            selected = [images[1]]
            downloader.return_value.download_all.assert_called_once_with(selected)
            metadata = (Path(tmpdir) / "ba" / "metadata.json").read_text(encoding="utf-8")
            self.assertIn("high.jpg", metadata)
            self.assertNotIn("low.jpg", metadata)


if __name__ == "__main__":
    unittest.main()
