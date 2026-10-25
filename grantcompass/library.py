"""Organisation library: turn uploaded files into text, and package the whole
library as the agents' source of truth.

The library goes into the agents' instructions in full, in a fixed order, so
it forms a stable prompt prefix the provider caches between runs. One
organisation's documents are small enough that this is cheaper and simpler
than a search index."""

import base64
import io

from . import db
from .config import MAX_INPUT_CHARS, MAX_UPLOAD_BYTES
from .profile import PROFILE_DOC_TITLE
from .profile import render as render_profile

DOC_TYPES = [
    "Mission & theory of change",
    "Programme description",
    "Programme report",
    "Budget",
    "Annual report",
    "Impact report",
    "Past application",
    "Monitoring & evaluation",
    "Governance",
    "Leadership bios",
    "Policy",
    "Approved organisational language",
    "Impact statistics",
    "Other",
]


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        from pypdf import PdfReader

        return "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        from docx import Document

        return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    raise ValueError("Upload a PDF, Word (.docx), text or Markdown file.")


def decode_upload(contents: str, filename: str) -> str:
    """dcc.Upload gives 'data:<mime>;base64,<data>'."""
    _, b64 = contents.split(",", 1)
    if len(b64) * 3 // 4 > MAX_UPLOAD_BYTES:  # size from the base64 length, before decoding anything
        raise ValueError(f"{filename} is over {MAX_UPLOAD_BYTES // 1_000_000} MB. Upload a smaller file, or "
                         "split it into parts.")
    text = extract_text(filename, base64.b64decode(b64)).strip()
    if not text:
        raise ValueError(f"No text found in {filename}. Scanned PDFs need to be converted to text first.")
    return text


def library_context() -> tuple[str, dict[str, str]]:
    """Return (prompt text, {title: content}). Raises if the library is empty or too big."""
    docs = sorted(db.list_documents(), key=lambda d: d["id"])  # stable order keeps the cached prefix stable
    prof = db.get_profile()
    if prof and any(prof["data"].values()):
        # The profile form comes first: it is the team's own structured summary.
        docs.insert(0, {"title": PROFILE_DOC_TITLE, "doc_type": "Organisation profile (form)",
                        "content": render_profile(prof["data"]), "approved": 0})
    # Answer Library entries are the team's approved wording, so the writers may adapt them.
    for ans in sorted(db.list_answers(), key=lambda x: x["id"]):
        docs.append({"title": f"Approved answer: {ans['question'][:80]}", "doc_type": "Approved answer (Answer Library)",
                     "content": f"Question: {ans['question']}\n\n{ans['text']}", "approved": 1})
    if not docs:
        raise ValueError("Fill in your Profile or upload a source document first (Profile menu → Source documents).")
    parts = []
    for d in docs:
        approved = ' approved="yes"' if d["approved"] else ""
        parts.append(f'<document title="{d["title"]}" type="{d["doc_type"]}"{approved}>\n{d["content"]}\n</document>')
    text = "\n\n".join(parts)
    if len(text) > MAX_INPUT_CHARS:
        raise ValueError(
            f"The library is {len(text):,} characters; the limit is {MAX_INPUT_CHARS:,}. Remove or shorten a document."
        )
    return text, {d["title"]: d["content"] for d in docs}
