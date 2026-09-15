"""Fetch the live SUPPORTED_LANGUAGES list from the deployed endpoint and
confirm the languages this evaluation wants to test are actually valid.

score.py returns {"error": ..., "supported_languages": [...]} when
language_id is invalid, so we deliberately send a bogus code to read that
list back rather than guessing or requiring the chatterbox package locally.
"""

import os
import sys

import requests

from config import DEFAULT_URL, DEFAULT_DEPLOYMENT

WANTED_LANGUAGES = ["en", "es", "fr", "de", "hi", "zh", "pt"]


def fetch_supported_languages(api_key: str, url: str, deployment_name: str) -> list[str]:
    # score.py returns {"error": ..., "supported_languages": [...]} for an
    # invalid language_id -- send the raw request directly (rather than
    # through invoke_chatterbox, which raises on the "error" key and
    # discards the rest of the body) so we can read that list back.
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if deployment_name:
        headers["azureml-model-deployment"] = deployment_name
    response = requests.post(
        url,
        json={"text": "probe", "language_id": "__probe__"},
        headers=headers,
        timeout=30.0,
    )
    response.raise_for_status()
    body = response.json()
    supported = body.get("supported_languages")
    if not supported:
        raise RuntimeError(f"Could not recover supported_languages from error body: {body}")
    return supported


def main() -> int:
    api_key = os.environ.get("CHATTERBOX_API_KEY", "")
    if not api_key:
        print("CHATTERBOX_API_KEY is not set", file=sys.stderr)
        return 1

    url = os.environ.get("CHATTERBOX_URL", DEFAULT_URL)
    deployment_name = os.environ.get("CHATTERBOX_DEPLOYMENT", DEFAULT_DEPLOYMENT)

    supported = fetch_supported_languages(api_key, url, deployment_name)
    print(f"Endpoint reports {len(supported)} supported languages: {supported}")

    missing = [lang for lang in WANTED_LANGUAGES if lang not in supported]
    if missing:
        print(f"MISMATCH: these requested codes are not in the supported list: {missing}", file=sys.stderr)
        print("Update WANTED_LANGUAGES / test_sentences.py with the correct codes before running evaluate.py.", file=sys.stderr)
        return 1

    print(f"All requested languages are valid: {WANTED_LANGUAGES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
