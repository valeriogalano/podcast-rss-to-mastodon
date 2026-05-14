import logging
import os

import requests

logger = logging.getLogger("github_state")


def update_github_variable(variable_name: str, value: str) -> None:
    """Aggiorna una variabile Actions del repository corrente via GitHub API.

    Richiede GH_TOKEN (fine-grained PAT con 'Variables: read and write')
    e GITHUB_REPOSITORY (impostato automaticamente da GitHub Actions).
    Se le variabili non sono disponibili, logga un warning e non fa nulla.
    """
    token = os.environ.get('GH_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')

    if not token or not repo:
        logger.warning(
            "GH_TOKEN o GITHUB_REPOSITORY non impostati: "
            "lo stato non verrà persistito su GitHub Variables."
        )
        return

    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    url = f"https://api.github.com/repos/{repo}/actions/variables/{variable_name}"

    response = requests.patch(url, headers=headers, json={"name": variable_name, "value": value})
    if response.status_code == 204:
        logger.debug(f"Variabile {variable_name} aggiornata.")
        return

    if response.status_code == 404:
        base_url = f"https://api.github.com/repos/{repo}/actions/variables"
        response = requests.post(base_url, headers=headers, json={"name": variable_name, "value": value})
        if response.status_code == 201:
            logger.debug(f"Variabile {variable_name} creata.")
            return

    raise RuntimeError(
        f"Impossibile aggiornare variabile {variable_name}: "
        f"{response.status_code} {response.text}"
    )
