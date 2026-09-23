"""Multi-turn scenario replay through the production reply pipeline.

Everything outside the model call is intercepted in-process: the catalog comes
from a read-only snapshot, Zoho/CRM/Wazzup/Telegram are recorders, and the only
network the harness permits is OpenRouter in live mode. See
``scripts/scenario_replay.py`` for the command line.
"""
