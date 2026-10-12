import pytest

from backend.app.services.preprocessing_service import (
    PDFValidationError,
    clean_paragraph,
    extract_pages,
    inspect_pdf,
    validate_pdf_upload,
)

from .conftest import make_pdf


def test_rejects_wrong_extension():
    with pytest.raises(PDFValidationError) as e:
        validate_pdf_upload("notes.txt", "application/pdf", b"%PDF-1.7")
    assert e.value.code == "invalid_extension"


def test_rejects_wrong_mime_type():
    with pytest.raises(PDFValidationError) as e:
        validate_pdf_upload("a.pdf", "image/png", b"%PDF-1.7")
    assert e.value.code == "invalid_mime_type"


def test_rejects_missing_pdf_header():
    with pytest.raises(PDFValidationError) as e:
        validate_pdf_upload("a.pdf", "application/pdf", b"hello world")
    assert e.value.code == "not_a_pdf"


def test_accepts_valid_header():
    validate_pdf_upload("Report.PDF", "application/pdf", b"%PDF-1.7\n...")


def test_corrupt_pdf_is_rejected(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.7\nthis is not really a pdf")
    with pytest.raises(PDFValidationError) as e:
        inspect_pdf(bad)
    assert e.value.code in ("unreadable_pdf", "empty_pdf")


def test_encrypted_pdf_is_rejected(tmp_path):
    path = make_pdf(tmp_path / "locked.pdf", ["secret text here"], encrypt=True)
    with pytest.raises(PDFValidationError) as e:
        inspect_pdf(path)
    assert e.value.code == "encrypted"


def test_extracts_pages_with_metadata(tmp_path):
    path = make_pdf(tmp_path / "doc.pdf", ["First page text about admissions.", "", "Third page about hostels."])
    assert inspect_pdf(path) == 3
    pages = extract_pages(path, "abcd" * 4, "doc.pdf")
    assert [p.page for p in pages] == [1, 2, 3]
    assert all(p.document_id == "abcd" * 4 and p.document_name == "doc.pdf" for p in pages)
    assert pages[0].has_text and "admissions" in pages[0].text
    assert not pages[1].has_text and pages[1].word_count == 0
    assert "hostels" in pages[2].text


def test_clean_paragraph_fixes_common_artifacts():
    assert clean_paragraph("ad-\nmission  is\n open") == "admission is open"
    assert clean_paragraph("ﬁnal") == "final"  # ligature
    assert clean_paragraph("soft­hyphen") == "softhyphen"
