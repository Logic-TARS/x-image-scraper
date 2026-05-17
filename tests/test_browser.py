import unittest

from xscrape.browser import (
    calculate_quality_score,
    extract_media_from_search_json,
    normalize_x_media_url,
    parse_compact_count,
    parse_like_count,
    select_quality_media,
    select_search_media,
)


class TestBrowserSearchHelpers(unittest.TestCase):
    def test_normalize_x_media_url_requests_original_quality(self):
        url = "https://pbs.twimg.com/media/abc?format=webp&name=small"
        self.assertEqual(
            normalize_x_media_url(url),
            "https://pbs.twimg.com/media/abc?format=jpg&name=orig",
        )

    def test_parse_compact_count(self):
        self.assertEqual(parse_compact_count("1.2K Likes"), 1200)
        self.assertEqual(parse_compact_count("3.4M"), 3_400_000)
        self.assertEqual(parse_compact_count("2万 いいね"), 20_000)
        self.assertEqual(parse_compact_count("7千"), 7_000)

    def test_parse_like_count_from_labels(self):
        self.assertEqual(parse_like_count(["Reply", "1.5K Likes. Like"]), 1500)
        self.assertEqual(parse_like_count(["返信", "2万 件のいいね"]), 20_000)
        self.assertEqual(parse_like_count(["답글", "345 좋아요"]), 345)

    def test_select_search_media_top_likes_then_time_order(self):
        items = [
            {"tweet_id": "old_high", "like_count": 100, "created_at": "2026-05-01T00:00:00Z"},
            {"tweet_id": "new_low", "like_count": 1, "created_at": "2026-05-16T00:00:00Z"},
            {"tweet_id": "new_high", "like_count": 90, "created_at": "2026-05-15T00:00:00Z"},
        ]

        selected = select_search_media(items, top=2, download_order="time")

        self.assertEqual([item["tweet_id"] for item in selected], ["new_high", "old_high"])

    def test_extract_media_from_search_json_reads_graphql_legacy_tweets(self):
        data = {
            "data": {
                "search_by_raw_query": {
                    "search_timeline": {
                        "timeline": {
                            "instructions": [
                                {
                                    "entries": [
                                        {
                                            "content": {
                                                "itemContent": {
                                                    "tweet_results": {
                                                        "result": {
                                                            "core": {
                                                                "user_results": {
                                                                    "result": {
                                                                        "legacy": {"screen_name": "artist"}
                                                                    }
                                                                }
                                                            },
                                                            "legacy": {
                                                                "id_str": "123",
                                                                "created_at": "Sat May 16 13:23:03 +0000 2026",
                                                                "full_text": "Blue Archive",
                                                                "favorite_count": 1500,
                                                                "retweet_count": 10,
                                                                "reply_count": 2,
                                                                "quote_count": 1,
                                                                "extended_entities": {
                                                                    "media": [
                                                                        {
                                                                            "type": "photo",
                                                                            "media_url_https": "https://pbs.twimg.com/media/abc.jpg",
                                                                            "original_info": {"width": 1200, "height": 1600},
                                                                        }
                                                                    ]
                                                                },
                                                            },
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }

        items = extract_media_from_search_json(data)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["tweet_id"], "123")
        self.assertEqual(items[0]["author_username"], "artist")
        self.assertEqual(items[0]["created_at"], "2026-05-16T13:23:03Z")
        self.assertEqual(items[0]["like_count"], 1500)
        self.assertEqual(items[0]["width"], 1200)
        self.assertEqual(items[0]["height"], 1600)
        self.assertGreater(items[0]["quality_score"], 1500)
        self.assertEqual(items[0]["url"], "https://pbs.twimg.com/media/abc.jpg?format=jpg&name=orig")

    def test_quality_score_rewards_resolution_and_penalizes_wip(self):
        finished = {"like_count": 1000, "retweet_count": 100, "quote_count": 10, "reply_count": 5, "width": 2000, "height": 2400, "text": "finished illustration"}
        sketch = {"like_count": 1400, "retweet_count": 100, "quote_count": 10, "reply_count": 5, "width": 800, "height": 800, "text": "wip sketch"}

        self.assertGreater(calculate_quality_score(finished), calculate_quality_score(sketch))

    def test_select_quality_media_uses_quality_score_before_likes(self):
        items = [
            {"tweet_id": "viral_sketch", "like_count": 5000, "retweet_count": 10, "created_at": "2026-05-16T00:00:00Z", "width": 600, "height": 600, "text": "wip sketch"},
            {"tweet_id": "finished", "like_count": 3000, "retweet_count": 600, "created_at": "2026-05-15T00:00:00Z", "width": 2200, "height": 2600, "text": "Blue Archive"},
        ]

        selected = select_quality_media(items, top=1, download_order="likes")

        self.assertEqual(selected[0]["tweet_id"], "finished")


if __name__ == "__main__":
    unittest.main()
