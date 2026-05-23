import os
from unittest.mock import MagicMock, patch

import pytest

from github_state import update_github_variable
from publish import (
    fetch_last_episode,
    is_published,
    normalize_template,
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

SAMPLE_RSS_NO_LINK = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Episodio senza link</title>
      <enclosure url="https://example.com/ep42.mp3" type="audio/mpeg" length="12345"/>
    </item>
  </channel>
</rss>"""


class TestNormalizeTemplate:
    def test_converts_literal_backslash_n(self):
        assert normalize_template("riga1\\nriga2") == "riga1\nriga2"

    def test_leaves_real_newlines_unchanged(self):
        assert normalize_template("riga1\nriga2") == "riga1\nriga2"

    def test_empty_string(self):
        assert normalize_template("") == ""


class TestIsPublished:
    def test_returns_true_when_link_matches(self):
        assert is_published("https://example.com/ep42", "https://example.com/ep42") is True

    def test_returns_false_when_link_differs(self):
        assert is_published("https://example.com/ep42", "https://example.com/ep41") is False

    def test_returns_false_when_last_url_empty(self):
        assert is_published("https://example.com/ep42", "") is False


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

    def test_fallback_to_enclosure_when_no_link(self):
        mock_resp = MagicMock()
        mock_resp.content = SAMPLE_RSS_NO_LINK
        with patch("publish.requests.get", return_value=mock_resp):
            episode = fetch_last_episode("https://feed.example.com/rss")
        assert episode["link"] == "https://example.com/ep42.mp3"

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
        return {
            "GH_TOKEN": "token123",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_ENVIRONMENT": "pensieriincodice",
        }

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
                update_github_variable("MY_VAR", "value")  # non deve sollevare

    def test_raises_when_env_vars_missing(self):
        env = {"GH_TOKEN": "", "GITHUB_REPOSITORY": "", "GITHUB_ENVIRONMENT": ""}
        with patch.dict(os.environ, env):
            with pytest.raises(RuntimeError, match="non impostati"):
                update_github_variable("MY_VAR", "value")
