import json
import os
from unittest.mock import MagicMock, patch

import pytest

from github_state import update_github_variable
from publish import (
    fetch_last_episode,
    is_published,
    load_podcasts_config,
    load_published_urls,
    publish_to_mastodon,
)

SAMPLE_RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <item>
      <title>Episodio 42</title>
      <link>https://example.com/ep42</link>
      <itunes:keywords>python, coding</itunes:keywords>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_NO_KEYWORDS = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Episodio senza tag</title>
      <link>https://example.com/ep1</link>
    </item>
  </channel>
</rss>"""


class TestLoadPublishedUrls:
    def test_returns_dict_from_env(self):
        data = {"pod1": "https://example.com/ep1"}
        with patch.dict(os.environ, {"LAST_PUBLISHED_URLS": json.dumps(data)}):
            result = load_published_urls()
        assert result == data

    def test_returns_empty_dict_when_env_missing(self):
        env = {k: v for k, v in os.environ.items() if k != "LAST_PUBLISHED_URLS"}
        with patch.dict(os.environ, env, clear=True):
            result = load_published_urls()
        assert result == {}

    def test_returns_empty_dict_on_invalid_json(self):
        with patch.dict(os.environ, {"LAST_PUBLISHED_URLS": "not-json"}):
            result = load_published_urls()
        assert result == {}


class TestIsPublished:
    def test_returns_true_when_link_matches(self):
        urls = {"pod1": "https://example.com/ep42"}
        assert is_published("https://example.com/ep42", "pod1", urls) is True

    def test_returns_false_when_link_differs(self):
        urls = {"pod1": "https://example.com/ep41"}
        assert is_published("https://example.com/ep42", "pod1", urls) is False

    def test_returns_false_when_podcast_missing(self):
        assert is_published("https://example.com/ep42", "pod1", {}) is False


class TestLoadPodcastsConfig:
    def test_loads_valid_json(self, tmp_path):
        config = [{"id": "p1", "name": "Podcast 1", "feed_url": "https://example.com/feed"}]
        config_file = tmp_path / "podcasts.json"
        config_file.write_text(json.dumps(config))
        result = load_podcasts_config(str(config_file))
        assert result == config

    def test_raises_when_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_podcasts_config(str(tmp_path / "missing.json"))


class TestFetchLastEpisode:
    def test_parses_title_link_hashtags(self):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_RSS
        with patch("publish.requests.get", return_value=mock_resp):
            episode = fetch_last_episode("https://feed.example.com/rss")
        assert episode["title"] == "Episodio 42"
        assert episode["link"] == "https://example.com/ep42"
        assert "#python" in episode["hashtags"]
        assert "#coding" in episode["hashtags"]

    def test_no_keywords_returns_empty_hashtags(self):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_RSS_NO_KEYWORDS
        with patch("publish.requests.get", return_value=mock_resp):
            episode = fetch_last_episode("https://feed.example.com/rss")
        assert episode["hashtags"] == ""

    def test_raises_on_empty_feed(self):
        empty_rss = b"""<?xml version="1.0"?><rss><channel></channel></rss>"""
        mock_resp = MagicMock()
        mock_resp.content = empty_rss
        with patch("publish.requests.get", return_value=mock_resp):
            with pytest.raises(Exception, match="Nessun episodio"):
                fetch_last_episode("https://feed.example.com/rss")


class TestPublishToMastodon:
    def test_sends_correct_request(self):
        episode = {"title": "Test Ep", "link": "https://ex.com/ep", "hashtags": "#test"}
        template = "Nuovo: {title}\n{link}\n{hashtags}"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("publish.requests.post", return_value=mock_resp) as mock_post:
            publish_to_mastodon(episode, "https://mastodon.example/api/v1/statuses", "TOKEN", template)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["data"]["status"] == "Nuovo: Test Ep\nhttps://ex.com/ep\n#test"

    def test_raises_on_api_error(self):
        episode = {"title": "Test", "link": "https://ex.com/ep", "hashtags": ""}
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("publish.requests.post", return_value=mock_resp):
            with pytest.raises(Exception, match="Errore Mastodon API"):
                publish_to_mastodon(episode, "https://mastodon.example/api/v1/statuses", "BAD_TOKEN", "{title}")


class TestUpdateGithubVariable:
    def _make_env(self):
        return {"GH_TOKEN": "token123", "GITHUB_REPOSITORY": "owner/repo"}

    def test_raises_on_401(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        with patch("github_state.requests.patch", return_value=mock_resp):
            with patch.dict(os.environ, self._make_env()):
                with pytest.raises(RuntimeError, match="401"):
                    update_github_variable("MY_VAR", "value")

    def test_raises_on_non_204_non_404(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server Error"
        with patch("github_state.requests.patch", return_value=mock_resp):
            with patch.dict(os.environ, self._make_env()):
                with pytest.raises(RuntimeError, match="500"):
                    update_github_variable("MY_VAR", "value")

    def test_creates_on_404(self):
        patch_resp = MagicMock()
        patch_resp.status_code = 404
        post_resp = MagicMock()
        post_resp.status_code = 201
        with patch("github_state.requests.patch", return_value=patch_resp), \
             patch("github_state.requests.post", return_value=post_resp):
            with patch.dict(os.environ, self._make_env()):
                update_github_variable("MY_VAR", "value")  # should not raise

    def test_skips_when_no_token(self):
        env = {"GH_TOKEN": "", "GITHUB_REPOSITORY": ""}
        with patch.dict(os.environ, env):
            update_github_variable("MY_VAR", "value")  # should not raise
