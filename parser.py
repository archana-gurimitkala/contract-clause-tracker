from collections import Counter
from pathlib import Path

import pdfplumber
from docx import Document

_HEADER_MAX_WORDS = 8
_HEADER_MIN_REPEATS = 3


def extract_text(file, filename=None):
    """Extract raw text from a PDF or DOCX contract.

    `file` can be a path (str/Path) or a file-like object (e.g. a Streamlit
    UploadedFile). When `file` is not a path, pass `filename` so the type
    can be detected from its extension.
    """
    name = filename or (file if isinstance(file, (str, Path)) else getattr(file, "name", ""))
    suffix = Path(name).suffix.lower()

    if suffix == ".pdf":
        text = _extract_pdf(file)
    elif suffix == ".docx":
        text = _extract_docx(file)
    else:
        raise ValueError(f"Unsupported file type: {suffix!r}. Use .pdf or .docx.")

    return _strip_running_headers(text)


def _strip_running_headers(text):
    """Remove short lines that repeat many times across the document — running
    page headers/footers (title repeated per page, "Page X of Y") that would
    otherwise interrupt a clause's text and break verbatim quote grounding."""
    lines = text.split("\n")
    counts = Counter(
        line.strip() for line in lines if line.strip() and len(line.strip().split()) <= _HEADER_MAX_WORDS
    )
    noise = {line for line, count in counts.items() if count >= _HEADER_MIN_REPEATS}
    if not noise:
        return text
    return "\n".join(line for line in lines if line.strip() not in noise)


def _extract_pdf(file):
    pages = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def _extract_docx(file):
    doc = Document(file)
    parts = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return "\n".join(parts)
