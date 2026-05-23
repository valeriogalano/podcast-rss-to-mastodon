# Piano: allinea podcast-rss-to-mastodon a podcast-rss-to-telegram

**Obiettivo:** fare in modo che il progetto mastodon funzioni esattamente come il gemello telegram, adattando solo la parte specifica dell'API di destinazione (Mastodon vs Telegram).

Il progetto telegram è più evoluto: usa GitHub Environments per isolare lo stato per podcast, gestione errori esplicita, architettura più pulita.

Procedere step-by-step chiedendo conferma dell'utente prima di ogni step.

---

## Step 1 — Riscrivere `publish.py`

- Rimuovere `load_podcasts_config()` e `load_published_urls()` (logica multi-podcast)
- Aggiungere `normalize_template()` (come telegram)
- Semplificare `is_published(link, last_url)` — firma identica a telegram (no dict, no podcast_id)
- Aggiungere fallback su `<enclosure>` in `fetch_last_episode()` quando `<link>` è assente
- Cambiare il blocco `__main__`: leggere config da env vars diretti (`RSS_URL`, `TEMPLATE`, `MASTODON_TOKEN`, `LAST_PUBLISHED_URL`) — un podcast per run
- Mantenere `publish_to_mastodon()` invariata

## Step 2 — Riscrivere `github_state.py`

- Aggiungere lettura di `GITHUB_ENVIRONMENT`
- Usare l'endpoint environment-scoped: `repos/{repo}/environments/{env}/variables`
- Sostituire la degradazione silenziosa (warning) con `RuntimeError` esplicito
- Log a livello `INFO`

## Step 3 — Riscrivere `.github/workflows/cron.yml`

- Sostituire il singolo job con due job separati: `pensieriincodice` e `goodvibrations`
- Ciascun job usa `environment: <nome>` per isolare le variabili
- Rimuovere lo step di generazione `podcasts.json`
- Passare le variabili direttamente: `RSS_URL`, `TEMPLATE`, `LAST_PUBLISHED_URL` (da `vars.*`), `MASTODON_TOKEN` (da `secrets.*`), `GH_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_ENVIRONMENT`

## Step 4 — Aggiornare `tests/test_publish.py`

- Rimuovere `TestLoadPublishedUrls` e `TestLoadPodcastsConfig`
- Aggiornare `TestIsPublished` alla nuova firma `(link, last_url)`
- Aggiungere test per il fallback `<enclosure>` in `TestFetchLastEpisode`
- Aggiungere `TestNormalizeTemplate`
- Aggiornare `TestPublishToMastodon` e `TestFetchLastEpisode`

## Step 5 — Configurare le variabili su GitHub

**Secrets a livello repo:**
- `MASTODON_TOKEN` — bearer token per l'API Mastodon
- `GH_TOKEN` — fine-grained PAT con permesso `Variables: read and write`

**Environment `pensieriincodice`:**
- `RSS_URL`, `TEMPLATE`, `LAST_PUBLISHED_URL` (inizialmente vuota)

**Environment `goodvibrations`:**
- `RSS_URL`, `TEMPLATE`, `LAST_PUBLISHED_URL` (inizialmente vuota)

---

**Stato:** Step 1–4 completati e testati (16/16 test verdi). In attesa di conferma utente per lo Step 5 (configurazione variabili su GitHub).
