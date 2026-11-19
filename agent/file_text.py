"""
Turn an uploaded audit-request file of (almost) any kind into plain text.

pdf                          pdfplumber
docx                         python-docx (paragraphs + tables)
xlsx / xlsm                  openpyxl (every sheet, cells joined with " | ")
doc / rtf / odt              LibreOffice headless -> txt (only if `soffice` is installed)
eml                          stdlib email (headers + text body)
html / htm / xml             tags stripped
txt / md / csv / tsv / log / json / anything else that decodes as text
Raises ValueError with a user-facing message if nothing readable comes out
(e.g. a scanned PDF or an image -- that would need OCR).
"""
import email
import io
import re
import shutil
import subprocess
import tempfile
from email import policy
from html.parser import HTMLParser
from pathlib import Path


class _Strip(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _decode(body: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            pass
    return body.decode("latin-1")


def _html(body: bytes) -> str:
    p = _Strip()
    p.feed(_decode(body))
    return re.sub(r"\n\s*\n+", "\n\n", "".join(p.parts)).strip()


def _pdf(body: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(body)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _docx(body: bytes) -> str:
    import docx
    d = docx.Document(io.BytesIO(body))
    out = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            out.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(out)


def _xlsx(body: bytes) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(body), read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"[{ws.title}]")
        for row in ws.iter_rows(values_only=True):
            if any(c is not None for c in row):
                out.append(" | ".join("" if c is None else str(c) for c in row))
    return "\n".join(out)


def _eml(body: bytes) -> str:
    m = email.message_from_bytes(body, policy=policy.default)
    head = "\n".join(f"{h}: {m[h]}" for h in ("From", "To", "Date", "Subject") if m[h])
    part = m.get_body(preferencelist=("plain", "html"))
    text = part.get_content() if part else ""
    if part is not None and part.get_content_type() == "text/html":
        text = _html(text.encode())
    return f"{head}\n\n{text}"


def _office(body: bytes, suffix: str) -> str:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise ValueError(f"{suffix} files need LibreOffice on the server to read; save it as .docx or .pdf and retry")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / f"in{suffix}"
        src.write_bytes(body)
        try:
            subprocess.run([soffice, "--headless", "--convert-to", "txt:Text", "--outdir", d, str(src)],
                           check=True, capture_output=True, timeout=90)
        except (subprocess.SubprocessError, OSError) as e:
            raise ValueError(f"could not convert the {suffix} file: {e}")
        out = Path(d) / "in.txt"
        return _decode(out.read_bytes()) if out.exists() else ""


def extract_text(filename: str, body: bytes) -> str:
    suffix = Path(filename or "").suffix.lower()
    try:
        if suffix == ".pdf":
            text = _pdf(body)
        elif suffix == ".docx":
            text = _docx(body)
        elif suffix in (".xlsx", ".xlsm"):
            text = _xlsx(body)
        elif suffix in (".doc", ".rtf", ".odt"):
            text = _office(body, suffix)
        elif suffix == ".eml":
            text = _eml(body)
        elif suffix in (".html", ".htm", ".xml"):
            text = _html(body)
        elif b"\x00" in body[:4096] and not body[:2] in (b"\xff\xfe", b"\xfe\xff"):
            raise ValueError(f"don't know how to read a {suffix or 'this'} file -- "
                             "use PDF, Word (.docx/.doc), Excel, email (.eml), HTML or a text file")
        else:
            text = _decode(body)  # txt, md, csv, tsv, log, json, unknown-but-text
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"could not read '{filename}': {e}")
    text = text.strip()
    if not text:
        raise ValueError(f"no readable text found in '{filename}' (a scanned PDF or an image would need OCR)")
    return text
