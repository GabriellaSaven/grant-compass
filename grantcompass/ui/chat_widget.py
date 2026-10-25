"""Compass Assistant: the chat in the bottom-right corner of every page.

Sending is two steps so the question appears at once: the first callback adds it to the
conversation; the second sees an unanswered question, asks the agent, and adds the reply."""

from urllib.parse import quote

from dash import ALL, Input, Output, State, callback, ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate

from ..assistant import ask
from ..errors import friendly

GREETING = "Let us help you, help others."
STARTERS = [
    "What should I work on this week?",
    "Which deadlines are coming up?",
    "Which grants are at risk, and why?",
    "Which new opportunities fit us best?",
    "What's still missing from our Miami Valley application?",
    "Who is responsible for what?",
]


def _svg(body: str, view: str = "0 0 32 32") -> str:
    return "data:image/svg+xml," + quote(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='{view}'>{body}</svg>")


# An open hand offering a heart: giving. The heart is a separate layer so it can lift and beat on hover.
HAND = _svg("<path d='M3 21.5h4.2l6.3 2.6c.9.4 1.9.4 2.8 0l11-5.2c1.2-.6.8-2.4-.5-2.4h-5.6l-4.8-1.7a5 5 0 0 0-1.7-.3H9.2"
            "L3 17.6' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>"
            "<path d='M14.6 19.4h5.6' fill='none' stroke='white' stroke-width='2' stroke-linecap='round'/>")
HEART = _svg("<path d='M16 14.6s-5.4-3.3-5.4-7.1c0-2.1 1.5-3.6 3.3-3.6 1 0 1.7.5 2.1 1.1.4-.6 1.1-1.1 2.1-1.1 1.8 0 3.3 1.5"
             " 3.3 3.6 0 3.8-5.4 7.1-5.4 7.1z' fill='#f2a08a'/>")
COIN = _svg("<circle cx='16' cy='16' r='13' fill='#e9c46a' stroke='#c9a24a' stroke-width='2'/>"
            "<text x='16' y='21' text-anchor='middle' font-family='Inter,Arial' font-weight='700' font-size='14'"
            " fill='#8a6a1f'>$</text>")
SUN = _svg("<circle cx='12' cy='12' r='4.2' fill='#e9b949'/>"
           + "".join(f"<line x1='12' y1='2.5' x2='12' y2='5' stroke='#e9b949' stroke-width='1.8' stroke-linecap='round'"
                     f" transform='rotate({a} 12 12)'/>" for a in range(0, 360, 45)), "0 0 24 24")


def _bubble(m: dict):
    if m["role"] == "user":
        return html.Div(html.Div(m["text"], className="chat-text"), className="chat-msg user")
    cls = "chat-msg bot" + (" error" if m.get("error") else "")
    return html.Div([html.Img(src=HEART, className="chat-avatar", alt=""),
                     dcc.Markdown(m["text"], className="chat-text", link_target="_blank")], className=cls)


def _welcome(chips: bool = True):
    return html.Div([
        html.Div(GREETING, className="chat-greeting"),
        html.P("Ask about deadlines, your pipeline, new funders or a draft. I can also take you to any page.",
               className="chat-intro"),
        html.Div([html.Button(s, id={"type": "chat-starter", "i": i}, n_clicks=0, className="chat-chip")
                  for i, s in enumerate(STARTERS)], className="chat-chips") if chips else None,
    ], className="chat-welcome")


def _log(history: list[dict]):
    items = [_welcome(chips=not history)] + [_bubble(m) for m in history]
    if history and history[-1]["role"] == "user":
        items.append(html.Div([html.Img(src=HEART, className="chat-avatar", alt=""),
                               html.Div([html.Span(), html.Span(), html.Span()], className="typing",
                                        title="Looking through your records…")], className="chat-msg bot"))
    return items


def widget():
    return html.Div([
        html.Button([
            html.Span([html.Img(src=COIN, className="ci-coin", alt=""), html.Img(src=HEART, className="ci-heart", alt=""),
                       html.Img(src=HAND, className="ci-hand", alt="")], className="ci"),
            html.Span("Ask Compass", className="chat-launch-label"),
        ], id="chat-launcher", className="chat-launcher", title="Ask Compass Assistant", **{"aria-label": "Open chat"}),
        html.Section([
            html.Div([
                html.Div([html.Img(src="/assets/logo.svg", className="chat-mark", alt=""), "Compass Assistant"],
                         className="chat-title"),
                html.Button("×", id="chat-close", className="chat-close", title="Close (Esc)",
                            **{"aria-label": "Close chat"}),
            ], className="chat-head"),
            html.Div(_log([]), id="chat-log", className="chat-log", **{"aria-live": "polite"}),
            html.Div([
                html.Img(src=SUN, className="chat-sun", alt=""),
                dcc.Textarea(id="chat-input", className="chat-input", rows=1, maxLength=2000,
                             placeholder="Ask me anything…"),
                html.Button("↑", id="chat-send", n_clicks=0, className="chat-send", title="Send (Enter)",
                            **{"aria-label": "Send"}),
            ], className="chat-composer"),
            html.Div("Enter to send · Shift+Enter for a new line", className="chat-hint"),
        ], id="chat-panel", className="chat-panel", role="dialog", **{"aria-label": "Compass Assistant"}),
        dcc.Store(id="chat-history", data=[], storage_type="session"),
    ], className="chat-root")


@callback(
    Output("chat-history", "data"),
    Output("chat-input", "value"),
    Input("chat-send", "n_clicks"),
    Input({"type": "chat-starter", "i": ALL}, "n_clicks"),
    State("chat-input", "value"),
    State("chat-history", "data"),
    prevent_initial_call=True,
)
def send(_n, starters, text, history):
    """Add the user's question; the reply follows in answer()."""
    history = list(history or [])
    if history and history[-1]["role"] == "user":  # still answering the last one
        raise PreventUpdate
    if isinstance(ctx.triggered_id, dict):
        if not any(starters):
            raise PreventUpdate
        text = STARTERS[ctx.triggered_id["i"]]
    text = (text or "").strip()
    if not text:
        raise PreventUpdate
    return history + [{"role": "user", "text": text}], ""


@callback(
    Output("chat-history", "data", allow_duplicate=True),
    Output("url", "pathname", allow_duplicate=True),
    Input("chat-history", "data"),
    running=[(Output("chat-send", "disabled"), True, False)],
    prevent_initial_call=True,
)
def answer(history):
    if not history or history[-1]["role"] != "user":
        raise PreventUpdate
    go = no_update
    try:
        res = ask(history[-1]["text"], history[:-1])
        reply = {"role": "bot", "text": res["text"]}
        go = res.get("navigate") or no_update  # the assistant opened a page for the user
    except ValueError as exc:
        reply = {"role": "bot", "text": str(exc), "error": True}
    except Exception as exc:
        reply = {"role": "bot", "error": True, "text": f"Sorry, I couldn't answer that. {friendly(exc)}"}
    return history + [reply], go


@callback(Output("chat-log", "children"), Input("chat-history", "data"))
def show(history):
    return _log(history or [])
