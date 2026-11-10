import pytest


def test_normalization_preserves_articles_with_stable_anchors():
    from app.legal.normalize import normalize

    raw = "Art. 1º Primeira regra.\n\nArt. 2º Segunda regra.".encode()
    document = normalize(raw, "text/markdown")
    assert len(document.sections) == 2
    assert document.sections[0].text == "Art. 1º Primeira regra."
    assert document == normalize(raw, "text/markdown")
    assert document.sections[0].anchor_id != document.sections[1].anchor_id


def test_html_scripts_are_not_indexed():
    from app.legal.normalize import normalize

    document = normalize(
        b"<article>Art. 1 Test rule.</article><script>secret()</script>", "text/html"
    )
    assert "secret" not in document.model_dump_json()


def test_empty_content_is_rejected():
    from app.legal.normalize import normalize

    with pytest.raises(ValueError):
        normalize(b"   ", "text/markdown")


def test_unknown_validity_is_not_assumed_current():
    from app.legal.schemas import IngestMetadata

    metadata = IngestMetadata(
        document_key="test",
        title="Test",
        official_url="https://example.org/law",
        version_label="original",
        authority="Test",
        norm_type="lei",
    )
    assert metadata.effective_from is None


def test_pdf_without_text_requires_manual_treatment():
    from io import BytesIO

    from app.legal.normalize import normalize
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(ValueError, match="sem texto"):
        normalize(stream.getvalue(), "application/pdf")


def test_invalid_normalized_document_rejected():
    from app.legal.schemas import LegalDocument
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        LegalDocument.model_validate({"sections": []})
