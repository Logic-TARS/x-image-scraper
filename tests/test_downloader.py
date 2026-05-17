import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


class FakeResponse:
    def __init__(self, url):
        self.content = f"content for {url}".encode("utf-8")

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=8192):
        yield self.content


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.proxies = {}

    def get(self, url, **_kwargs):
        return FakeResponse(url)


class TestImageDownloader(unittest.TestCase):
    def import_downloader_with_fake_requests(self):
        fake_requests = types.SimpleNamespace(
            RequestException=Exception,
            Session=FakeSession,
        )
        sys.modules.pop("xscrape.downloader", None)
        with mock.patch.dict(sys.modules, {"requests": fake_requests}):
            return importlib.import_module("xscrape.downloader")

    def test_download_all_reports_progress_and_clears_pending(self):
        downloader_module = self.import_downloader_with_fake_requests()

        with tempfile.TemporaryDirectory() as tmpdir:
            downloader = downloader_module.ImageDownloader(tmpdir, workers=1)
            item = {"url": "https://example.com/image.jpg", "tweet_id": "1", "type": "photo"}
            progress = []

            stats = downloader.download_all(
                [item],
                on_progress=lambda done, total, current_stats: progress.append((done, total, current_stats.copy())),
                show_progress=False,
            )

            self.assertEqual(stats, {"downloaded": 1, "skipped": 0, "failed": 0})
            self.assertEqual(progress, [(1, 1, {"downloaded": 1, "skipped": 0, "failed": 0})])
            self.assertFalse((Path(tmpdir) / "pending_downloads.json").exists())
            self.assertTrue((Path(tmpdir) / "1_image.jpg").exists())

    def test_download_all_merges_pending_items(self):
        downloader_module = self.import_downloader_with_fake_requests()

        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending_downloads.json"
            pending = [{"url": "https://example.com/pending.jpg", "tweet_id": "2", "type": "photo"}]
            pending_file.write_text(json.dumps(pending), encoding="utf-8")

            downloader = downloader_module.ImageDownloader(tmpdir, workers=1)
            item = {"url": "https://example.com/image.jpg", "tweet_id": "1", "type": "photo"}
            items = [item]
            progress = []

            stats = downloader.download_all(
                items,
                on_progress=lambda done, total, _stats: progress.append((done, total)),
                show_progress=False,
            )

            self.assertEqual(stats, {"downloaded": 2, "skipped": 0, "failed": 0})
            self.assertEqual(progress, [(1, 2), (2, 2)])
            self.assertEqual(items, [item])
            self.assertFalse(pending_file.exists())
            self.assertTrue((Path(tmpdir) / "1_image.jpg").exists())
            self.assertTrue((Path(tmpdir) / "2_pending.jpg").exists())


if __name__ == "__main__":
    unittest.main()
