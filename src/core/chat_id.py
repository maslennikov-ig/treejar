"""The customer's real WhatsApp id inside a stored conversation phone."""


def base_chat_id(chat_id: str) -> str:
    """Drop a repo-owned ``#suffix`` from a stored chat id.

    Conversations may carry ``<phone>#<tag>`` for an isolated test dialogue
    or ``<phone>#archived-...`` after a reset. Only the part before ``#`` is
    the customer's number, so anything shown to the customer or sent to an
    outside system uses it.
    """
    value = chat_id.strip()
    base, _, suffix = value.partition("#")
    if suffix and base:
        return base
    return value
