"""Shared defaults for the deployed Chatterbox endpoint, used by evaluate.py,
chatterbox_invocation.py, and resolve_languages.py so there is one place to
update if the endpoint moves."""

DEFAULT_URL = "https://mlonlep-rwai-ctbx-dev-wus.westus.inference.ml.azure.com/score"
DEFAULT_DEPLOYMENT = "chatterbox-v1"
