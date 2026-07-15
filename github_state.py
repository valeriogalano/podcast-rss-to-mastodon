import logging
import os

import requests

logger = logging.getLogger("github_state")


def update_github_variable(variable_name: str, value: str) -> None:
    """Aggiorna una variabile Actions dell'environment corrente via GitHub API.

    Richiede GH_TOKEN (fine-grained PAT con 'Variables: read and write'),
    GITHUB_REPOSITORY e GITHUB_ENVIRONMENT (impostati dal workflow).
    """
    token = os.environ.get('GH_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    environment = os.environ.get('GITHUB_ENVIRONMENT')

    if not token or not repo or not environment:
        raise RuntimeError(
            "GH_TOKEN, GITHUB_REPOSITORY o GITHUB_ENVIRONMENT non impostati: "
            "impossibile persistere lo stato su GitHub Variables."
        )

    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    base_url = f"https://api.github.com/repos/{repo}/environments/{environment}/variables"
    url = f"{base_url}/{variable_name}"

    response = requests.patch(url, headers=headers, json={"name": variable_name, "value": value})
    if response.status_code == 204:
        logger.info(f"Variabile {variable_name} aggiornata.")
        return

    if response.status_code == 404:
        response = requests.post(base_url, headers=headers, json={"name": variable_name, "value": value})
        if response.status_code == 201:
            logger.info(f"Variabile {variable_name} creata.")
            return

    raise RuntimeError(
        f"Impossibile aggiornare variabile {variable_name}: "
        f"{response.status_code} {response.text}"
    )
