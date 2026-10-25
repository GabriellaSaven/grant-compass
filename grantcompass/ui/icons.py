"""Line icons for what a funder mainly supports, drawn in the text colour (CSS mask), so they suit any theme."""

from urllib.parse import quote

from dash import html

from ..triage import FOCUS_TERMS

PATHS = {
    "tree": "M12 3a5 5 0 0 1 4.6 7A4 4 0 0 1 15 18H9a4 4 0 0 1-1.6-8A5 5 0 0 1 12 3zM12 18v4M12 13l-2-2M12 15l2.5-2.5",
    "heart": "M20.8 5.6a5 5 0 0 0-7.1 0L12 7.3l-1.7-1.7a5 5 0 0 0-7.1 7.1L12 21.5l8.8-8.8a5 5 0 0 0 0-7.1zM6.5 12h3l1.5-3 "
             "2 5 1.5-2h3",
    "book": "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 21V5M8 7h7M8 10.5h5",
    "cap": "M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5M22 9v6",
    "sprout": "M12 22V11M12 11C12 7 9 5 4 5c0 4 3 6 8 6zM12 14c0-4 3-6 8-6 0 4-3 6-8 6z",
    "briefcase": "M3 8h18v12H3zM8 8V5h8v3M3 13h18",
    "wheat": "M12 22V7M12 7c-2-2-2-3.5 0-5 2 1.5 2 3 0 5zM12 12c-3 0-5-1.8-5-4 3 0 5 1.8 5 4zM12 12c3 0 5-1.8 5-4-3 0-5 "
             "1.8-5 4zM12 17c-3 0-5-1.8-5-4 3 0 5 1.8 5 4zM12 17c3 0 5-1.8 5-4-3 0-5 1.8-5 4z",
    "house": "M3 11l9-7 9 7M5 9.5V20h14V9.5M10 20v-6h4v6",
    "palette": "M12 3a9 9 0 1 0 0 18c1.4 0 2-1 2-2 0-1.5-1.5-2-1.5-3.5S13.8 13 15.3 13H18a3 3 0 0 0 3-3c0-4-4-7-9-7z"
               "M7.5 11.5h.01M9.5 7.5h.01M14.5 7.5h.01",
    "coin": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM15 8.7c-.6-1-1.7-1.6-3-1.6-1.7 0-3 .9-3 2.2 0 3 6 1.6 6 4.6 0 1.3-1.3"
            " 2.2-3 2.2-1.4 0-2.6-.6-3.2-1.6M12 5.5v13",
    "landmark": "M3 21h18M5 21V11M9.5 21V11M14.5 21V11M19 21V11M2 11l10-7 10 7z",
    "globe": "M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM2 12h20M12 2c2.8 3 4 6.5 4 10s-1.2 7-4 10c-2.8-3-4-6.5-4-10s1.2-7"
             " 4-10z",
    "people": "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a6 6 0 0 1 12 0v1M16 3.5a4 4 0 0 1 0 7.5M22 21v-1a6 6 0 0 0-4-5.6",
    "scale": "M12 3v18M6 21h12M4 7h16M7 7l-3.5 7a3.5 3.5 0 0 0 7 0zM17 7l-3.5 7a3.5 3.5 0 0 0 7 0z",
    "flask": "M9 2h6M10 2v6L4.2 18.6A2 2 0 0 0 6 21.5h12a2 2 0 0 0 1.8-2.9L14 8V2M7 15h10",
}
FOCUS_ICON = {
    "Early childhood": "sprout", "K-12 education": "cap", "Literacy": "book", "Youth development": "sprout",
    "Higher education & workforce": "briefcase", "Health": "heart", "Mental health": "heart",
    "Food security": "wheat", "Housing & homelessness": "house", "Arts & culture": "palette",
    "Environment": "tree", "Economic mobility": "coin", "Civic engagement": "landmark",
    "Immigrant & refugee services": "globe", "Disability services": "people", "Racial equity": "scale",
    "Women & girls": "people", "Older adults": "people",
}


def _url(name: str) -> str:
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
           f"stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='{PATHS[name]}'/></svg>")
    return f'url("data:image/svg+xml,{quote(svg)}")'


def main_field(lead: dict) -> str | None:
    """The focus area a funder's own words mention most (title counts double); None if nothing matches."""
    title = (lead.get("title") or "").lower()
    body = " ".join(str(lead.get(k) or "") for k in ("summary", "categories", "focus_area", "raw_text")).lower()
    scores = {area: sum(2 * title.count(t) + body.count(t) for t in terms) for area, terms in FOCUS_TERMS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else None


def field_icon(lead: dict):
    """A small icon for what the funder mainly supports, with the field named on hover."""
    area = main_field(lead)
    name = FOCUS_ICON.get(area, "landmark")
    url = _url(name)
    return html.Span(className="field-icon", title=f"Mainly funds: {area}" if area else "General funder",
                     style={"WebkitMaskImage": url, "maskImage": url})
