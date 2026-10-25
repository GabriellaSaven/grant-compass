"""Turn exceptions into one plain-English sentence for the screen. The full error still goes to the
server log, so nothing is hidden from a developer; the user just never sees a stack trace."""

import logging
from urllib.parse import urlparse

import requests

log = logging.getLogger("grantcompass")

HTTP_MESSAGES = {
    401: "That site doesn't allow automated reading. Copy the page text into the box instead.",
    403: "That site doesn't allow automated reading. Copy the page text into the box instead.",
    404: "That page wasn't found (404). Check the link, or copy the page text into the box instead.",
    429: "That site is limiting requests right now. Try again in a minute.",
}


def friendly(exc: Exception) -> str:
    """One sentence a grant writer can act on."""
    if isinstance(exc, ValueError):  # our own checks already speak plain English
        return str(exc)
    log.exception("Shown to the user as a friendly error", exc_info=exc)
    name = type(exc).__name__
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        code = exc.response.status_code
        return HTTP_MESSAGES.get(code, "That site is having problems right now. Try again later, or paste the "
                                       "text instead." if code >= 500 else f"That page couldn't be read ({code}).")
    if isinstance(exc, requests.Timeout):
        return "The site took too long to answer. Try again, or copy the page text into the box instead."
    if isinstance(exc, requests.ConnectionError):
        host = urlparse(getattr(exc.request, "url", "") or "").netloc
        return f"Couldn't reach {host or 'that site'}. Check the link and your internet connection."
    if name == "ModelHTTPError" and "content_filter" in str(getattr(exc, "body", "") or exc):
        return ("The AI provider refused this text because it looks like an attempt to manipulate the AI "
                "(prompt injection). Nothing was saved. If it's a genuine funder page, paste just the "
                "relevant part.")
    if name == "UsageLimitExceeded":
        return ("This request hit the app's per-run limit on AI calls and was stopped to protect your budget. "
                "Try a simpler question or a shorter document.")
    if name in ("AuthenticationError", "PermissionDeniedError"):
        return "The AI service rejected the API key. Check PORTKEY_API_KEY in your .env file."
    if name in ("APIConnectionError", "APITimeoutError"):
        return "Couldn't reach the AI service. Check your internet connection and try again."
    if name == "RateLimitError":
        return "The AI service is busy. Wait a moment and try again."
    return f"Something went wrong ({name}). Please try again."
