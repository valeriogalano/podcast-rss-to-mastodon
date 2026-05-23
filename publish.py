import logging
import os
import re
import xml.etree.ElementTree as ET

import requests

from github_state import update_github_variable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mastodon")

ITUNES_NS = 'http://www.itunes.com/dtds/podcast-1.0.dtd'


def normalize_template(template: str) -> str:
    return template.replace('\\n', '\n')


def fetch_last_episode(feed_url: str) -> dict:
    response = requests.get(feed_url)
    response.raise_for_status()

    root = ET.fromstring(response.content)
    item = root.find('./channel/item')

    if item is None:
        raise Exception("Nessun episodio trovato nel feed")

    title = item.findtext('title', '').strip()
    link = item.findtext('link', '').strip()

    if not link:
        enclosure = item.find('enclosure')
        if enclosure is not None:
            link = enclosure.get('url', '').strip()

    if not title or not link:
        raise Exception(f"Titolo o link mancante: {title=} {link=}")

    keywords_el = item.find(f'{{{ITUNES_NS}}}keywords')
    hashtags = ''
    if keywords_el is not None and keywords_el.text:
        hashtags = ' '.join(
            '#' + re.sub(r'\s+', '', kw.strip())
            for kw in keywords_el.text.split(',')
            if kw.strip()
        )

    return {'title': title, 'link': link, 'hashtags': hashtags}


def is_published(link: str, last_published_url: str) -> bool:
    return last_published_url == link


def publish_to_mastodon(episode: dict, api_url: str, token: str, template: str) -> None:
    content = template \
        .replace('{title}', episode['title']) \
        .replace('{link}', episode['link']) \
        .replace('{hashtags}', episode['hashtags'])

    logger.info(f"Pubblicazione su Mastodon: {content[:80]}...")

    response = requests.post(
        api_url,
        headers={'Authorization': f'Bearer {token}'},
        data={'status': content}
    )

    if response.status_code not in (200, 201):
        raise Exception(f"Errore Mastodon API {response.status_code}: {response.text}")

    logger.info("Post pubblicato con successo!")


if __name__ == "__main__":
    token = os.environ['MASTODON_TOKEN']
    api_url = os.environ.get('MASTODON_API_URL', 'https://mastodon.uno/api/v1/statuses')
    rss_url = os.environ['RSS_URL']
    template = normalize_template(os.environ['TEMPLATE'])
    last_published_url = os.environ.get('LAST_PUBLISHED_URL', '')

    episode = fetch_last_episode(rss_url)
    logger.info(f"Ultimo episodio: {episode['link']}")

    if is_published(episode['link'], last_published_url):
        logger.info("Episodio già pubblicato, skip.")
    else:
        publish_to_mastodon(episode, api_url, token, template)
        update_github_variable('LAST_PUBLISHED_URL', episode['link'])
        logger.info("Stato aggiornato.")
