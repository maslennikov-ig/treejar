import pytest

from src.services.pdf.generator import generate_pdf


@pytest.mark.asyncio
async def test_generate_pdf():
    pdf_bytes = await generate_pdf("<h1>Hello</h1>")
    assert pdf_bytes.startswith(b"%PDF-")
