import asyncio
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML  # type: ignore[import-untyped]

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates" / "quotation"


async def generate_pdf(html_content: str) -> bytes:
    """
    Generates a PDF from an HTML string using WeasyPrint.
    Runs synchronously in a threadpool to avoid blocking the event loop.
    """

    def _render() -> bytes:
        return HTML(string=html_content).write_pdf()  # type: ignore[no-any-return]

    return await asyncio.to_thread(_render)


def render_quotation_html(context: dict[str, object]) -> str:
    """
    Renders the quotation HTML template with the given context.
    Also injects the CSS content directly to ensure it works correctly with WeasyPrint.
    """
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("template.html")

    # Read the CSS to inject
    css_path = TEMPLATE_DIR / "style.css"
    custom_css = ""
    if css_path.exists():
        custom_css = css_path.read_text(encoding="utf-8")

    # Inject CSS into context
    context["custom_css"] = custom_css

    return template.render(context)
