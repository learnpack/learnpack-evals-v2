"""What every caller of Clerk's REST API meets: the base URL, the deadline, the refusal.

Two adapters speak it — creating the invitation when an admin invites somebody
(`modules/identity/infrastructure/dispatchers.py`) and writing the instance's JWT template
before anybody signs in (`clerk_instance.py`).

The refusal is why this is a module and not a constant. Clerk answers one with a sentence
written for a human, and an adapter that drops it hands an operator "delivery failed" where
"that address is already a Clerk user" was sitting in the response. Both callers want that
sentence and neither wants to parse the envelope again — while the words around it differ per
act, so composing the final message stays with the caller.

Not `clerk.py`, which verifies the tokens this configures.
"""

import httpx

API_BASE = "https://api.clerk.com/v1"

# Long enough for a slow provider, short enough that nobody is left watching a spinner over an
# act that has already been committed on our side.
TIMEOUT_SECONDS = 10.0


def error_sentence(response: httpx.Response) -> str:
    """Clerk's own words for a refusal, or `""` when it offered none.

    Its errors arrive as `{"errors": [{"message", "long_message", ...}]}`. `long_message` is
    the one written for a person to act on, so it wins where both are present.
    """
    try:
        errors = response.json().get("errors") or []
        return "; ".join(
            e.get("long_message") or e.get("message") or "" for e in errors if isinstance(e, dict)
        ).strip("; ")
    except (ValueError, AttributeError):
        return ""
