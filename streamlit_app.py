"""Interactive Streamlit page for manually testing the deployed Chatterbox
Multilingual TTS endpoint: upload a reference clip, pick a language and an
emotion preset (or dial the knobs by hand), generate, then play/download.

This is a manual-testing convenience, not part of the eval pipeline.

Deployment note: this is a flattened, self-contained copy of
eval/streamlit_app.py from the main repo, meant to be pushed to its own
minimal git repo and deployed on Streamlit Community Cloud (or any other
Streamlit host) so it runs on an always-on server instead of a local
machine + tunnel. CHATTERBOX_API_KEY should be set via that host's secrets
mechanism (e.g. Streamlit Cloud's "Secrets" panel), never committed to git.
"""

import base64
import os

import requests
import streamlit as st

from chatterbox_invocation import ChatterboxError, invoke_chatterbox
from config import DEFAULT_DEPLOYMENT, DEFAULT_URL
from resolve_languages import WANTED_LANGUAGES
import emotion  # noqa: E402 -- the clinical-distress-to-dial mapping shared with hs-voice-bridge

PRESET_NAMES = ["Custom"] + sorted(emotion.PRESETS)

st.set_page_config(page_title="Chatterbox TTS Tester", page_icon="🗣️")
st.title("🗣️ Chatterbox Multilingual TTS Tester")


def _apply_preset() -> None:
    preset = st.session_state["preset"]
    if preset == "Custom":
        return
    params = emotion.params_for_preset(preset)
    st.session_state["exaggeration"] = params["exaggeration"]
    st.session_state["cfg_weight"] = params["cfg_weight"]
    st.session_state["temperature"] = params["temperature"]


def _get_secret(name: str, default: str = "") -> str:
    """Prefer the host's secrets store (e.g. Streamlit Cloud's Secrets panel)
    over a plain environment variable, without blowing up when no secrets
    file exists at all (e.g. running this locally)."""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name, default)


# Endpoint credentials/URL are operator-only config, never shown to or entered by
# whoever is using this page -- sourced entirely from the host's secrets/environment.
api_key = _get_secret("CHATTERBOX_API_KEY")
url = _get_secret("CHATTERBOX_URL", DEFAULT_URL)
deployment_name = _get_secret("CHATTERBOX_DEPLOYMENT", DEFAULT_DEPLOYMENT)

if not api_key:
    st.error("CHATTERBOX_API_KEY is not set. Add it in this app's Secrets settings and reboot the app.")
    st.stop()

text = st.text_area(
    "Text to synthesize",
    value="Hello, this is a test message for Chatterbox text to speech.",
    height=100,
)

reference_clip = st.file_uploader("Reference clip for voice cloning (WAV)", type=["wav"])

language_id = st.selectbox("Output language", WANTED_LANGUAGES)

st.selectbox("Emotion preset (quick-fill the knobs below)", PRESET_NAMES, key="preset", on_change=_apply_preset)

for _field, _default in emotion.NEUTRAL.items():
    st.session_state.setdefault(_field, _default)

col1, col2, col3 = st.columns(3)
with col1:
    exaggeration = st.slider(
        "Exaggeration",
        min_value=emotion.EXAG_MIN,
        max_value=emotion.EXAG_MAX,
        key="exaggeration",
    )
with col2:
    cfg_weight = st.slider(
        "CFG weight",
        min_value=emotion.CFG_MIN,
        max_value=emotion.CFG_MAX,
        key="cfg_weight",
    )
with col3:
    temperature = st.slider(
        "Temperature",
        min_value=emotion.TEMP_MIN,
        max_value=emotion.TEMP_MAX,
        key="temperature",
    )

if st.button("Generate speech", type="primary"):
    if not text.strip():
        st.error("Text to synthesize must not be empty.")
    else:
        audio_prompt_base64 = (
            base64.b64encode(reference_clip.getvalue()).decode("utf-8") if reference_clip else None
        )
        try:
            with st.spinner("Calling Chatterbox endpoint..."):
                result = invoke_chatterbox(
                    text=text,
                    api_key=api_key,
                    url=url,
                    language_id=language_id,
                    audio_prompt_base64=audio_prompt_base64,
                    exaggeration=exaggeration,
                    cfg_weight=cfg_weight,
                    temperature=temperature,
                    deployment_name=deployment_name or None,
                )
        except ChatterboxError as e:
            st.error(f"Endpoint rejected the request: {e}")
        except requests.RequestException as e:
            st.error(f"Request to the endpoint failed: {e}")
        else:
            wav_bytes = base64.b64decode(result["audio_base64"])
            st.success("Generated.")
            st.audio(wav_bytes, format="audio/wav")
            preset_label = st.session_state["preset"].lower() if st.session_state["preset"] != "Custom" else "custom"
            st.download_button(
                "Download WAV",
                data=wav_bytes,
                file_name=f"chatterbox_{language_id}_{preset_label}.wav",
                mime="audio/wav",
            )
