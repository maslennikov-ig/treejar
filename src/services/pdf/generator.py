import asyncio
from weasyprint import HTML

async def generate_pdf(html_content: str) -> bytes:
    """
    Generates a PDF from an HTML string using WeasyPrint.
    Runs synchronously in a threadpool to avoid blocking the event loop.
    """
    def _render() -> bytes:
        return HTML(string=html_content).write_pdf()  # type: ignore[no-any-return]
        
    return await asyncio.to_thread(_render)
