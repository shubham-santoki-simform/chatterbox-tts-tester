---
title: Chatterbox TTS Tester
emoji: 🗣️
colorFrom: purple
colorTo: indigo
sdk: streamlit
sdk_version: 1.63.0
app_file: streamlit_app.py
pinned: false
---

# Chatterbox Multilingual TTS Tester

Internal testing UI for the Chatterbox Multilingual TTS endpoint: upload a WAV reference clip,
pick a language and an emotion preset (or dial the knobs by hand), generate, then play/download.

## Setup

This app needs one secret/environment variable set:

- `CHATTERBOX_API_KEY` — the Chatterbox endpoint's API key.

Optional (only needed to point at a different endpoint/deployment than the default in `config.py`):

- `CHATTERBOX_URL`
- `CHATTERBOX_DEPLOYMENT`

On Streamlit Community Cloud, set these under the app's **Settings → Secrets**. On Hugging Face
Spaces, set them under **Settings → Variables and secrets** (note: the "Streamlit" SDK card may not
appear in every account's "New Space" flow — if so, this same `streamlit_app.py` also runs fine on
Streamlit Community Cloud, or any other host that can run `streamlit run streamlit_app.py`).
