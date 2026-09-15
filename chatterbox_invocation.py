"""Invoke the Chatterbox Multilingual TTS Azure ML online endpoint.

Request/response schema here is taken directly from the deployed scoring
script (chatterbox-tts-endpoint/deployment/score.py), not guessed:

    request  {text, language_id, audio_prompt_base64?, exaggeration?,
              cfg_weight?, temperature?}
    response {audio_base64, sample_rate, format: "wav", language_id}
             or {"error": "..."} (score.py can return an error body with a
             2xx status for request-validation failures, so callers must
             check for an "error" key rather than trusting response.ok alone)
"""

import argparse
import json
import os
from typing import Any, Optional

import requests

from config import DEFAULT_URL, DEFAULT_DEPLOYMENT


class ChatterboxError(RuntimeError):
    """Raised when the endpoint returns a validation/error body."""


def invoke_chatterbox(
    text: str,
    api_key: str,
    url: str = DEFAULT_URL,
    language_id: str = "en",
    audio_prompt_base64: Optional[str] = None,
    exaggeration: Optional[float] = None,
    cfg_weight: Optional[float] = None,
    temperature: Optional[float] = None,
    deployment_name: Optional[str] = DEFAULT_DEPLOYMENT,
    timeout: float = 60.0,
) -> dict:
    """Call the Chatterbox TTS endpoint and return the parsed JSON response.

    Args:
        text: Text to synthesize.
        api_key: Primary/secondary key, AMLToken, or Microsoft Entra ID token for the endpoint.
        url: Endpoint scoring URL.
        language_id: One of score.py's SUPPORTED_LANGUAGES (see resolve_languages.py
            to fetch the live list from the endpoint itself).
        audio_prompt_base64: Base64-encoded WAV reference clip for zero-shot voice
            cloning (<=10MB decoded). Omit for the default voice.
        exaggeration: Emotional intensity, 0.0-2.0 (endpoint default 0.5).
        cfg_weight: Pacing/deliberateness, 0.0-1.0 (endpoint default 0.5).
        temperature: Delivery variability, 0.0-2.0 (endpoint default 0.8).
        deployment_name: Specific deployment to target via the
            "azureml-model-deployment" header. Pass None to let the
            endpoint's traffic rules decide.
        timeout: Request timeout in seconds.

    Returns:
        The parsed JSON response body: {"audio_base64", "sample_rate", "format", "language_id"}.

    Raises:
        ValueError: If api_key or text is empty.
        ChatterboxError: If the endpoint returns an {"error": ...} body.
        requests.HTTPError: If the HTTP request itself fails.
    """
    if not api_key:
        raise ValueError("A key should be provided to invoke the endpoint")
    if not text or not text.strip():
        raise ValueError("text must be non-empty")

    request_body: dict[str, Any] = {"text": text, "language_id": language_id}
    if exaggeration is not None:
        request_body["exaggeration"] = exaggeration
    if cfg_weight is not None:
        request_body["cfg_weight"] = cfg_weight
    if temperature is not None:
        request_body["temperature"] = temperature
    if audio_prompt_base64:
        request_body["audio_prompt_base64"] = audio_prompt_base64

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if deployment_name:
        headers["azureml-model-deployment"] = deployment_name

    response = requests.post(url, json=request_body, headers=headers, timeout=timeout)

    if not response.ok:
        print("Response headers:", dict(response.headers))
        print("Response body:", response.text)
        response.raise_for_status()

    result = response.json()
    if isinstance(result, dict) and "error" in result:
        raise ChatterboxError(result["error"])
    return result


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Invoke the Chatterbox TTS endpoint")
    parser.add_argument("--text", default="Hello, this is a test message for Chatterbox text to speech.")
    parser.add_argument("--api-key", default=os.environ.get("CHATTERBOX_API_KEY", ""))
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--language-id", default="en")
    parser.add_argument("--audio-prompt-path", default=None, help="Local WAV file for voice cloning")
    parser.add_argument("--exaggeration", type=float, default=None)
    parser.add_argument("--cfg-weight", type=float, default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--deployment-name", default=DEFAULT_DEPLOYMENT)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser.parse_args()


if __name__ == "__main__":
    from audio_utils import encode_reference_clip

    args = _parse_args()
    audio_prompt_b64 = encode_reference_clip(args.audio_prompt_path) if args.audio_prompt_path else None
    result = invoke_chatterbox(
        text=args.text,
        api_key=args.api_key,
        url=args.url,
        language_id=args.language_id,
        audio_prompt_base64=audio_prompt_b64,
        exaggeration=args.exaggeration,
        cfg_weight=args.cfg_weight,
        temperature=args.temperature,
        deployment_name=args.deployment_name,
        timeout=args.timeout,
    )
    printable = {k: v for k, v in result.items() if k != "audio_base64"}
    printable["audio_base64_len"] = len(result.get("audio_base64", ""))
    print(json.dumps(printable, indent=2))
