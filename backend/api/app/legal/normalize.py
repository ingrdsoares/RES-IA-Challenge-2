import hashlib
import re
from io import BytesIO

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.legal.schemas import LegalDocument, Section


def normalize(raw: bytes, media_type: str) -> LegalDocument:
    if media_type == "application/pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(raw)).pages)
    elif media_type == "text/html":
        soup = BeautifulSoup(raw, "html.parser")
        for element in soup(["script", "style", "nav"]):
            element.decompose()
        text = soup.get_text("\n", strip=True)
    elif media_type in ("text/markdown", "text/plain"):
        text = raw.decode("utf-8-sig")
    else:
        raise ValueError("Formato não suportado")
    text = text.replace("\r\n", "\n").strip()
    if not text:
        raise ValueError("Documento sem texto extraível; tratamento manual necessário")
    # Preserve articles; bound long passages while retaining deterministic anchors.
    articles = re.split(r"(?m)(?=^\s*(?:#+\s*)?Art\.?\s+\d)", text)
    sections = []
    for article in articles:
        article = article.strip()
        for offset in range(0, len(article), 3000):
            body = article[offset : offset + 3000].strip()
            if body:
                anchor = f"s{len(sections) + 1}-" + hashlib.sha256(body.encode()).hexdigest()[:12]
                sections.append(Section(anchor_id=anchor, text=body))
    return LegalDocument(sections=sections)
