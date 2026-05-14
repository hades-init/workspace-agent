import re
import logging
from html2text import HTML2Text


logger = logging.getLogger(__name__)


def _build_text_maker() -> HTML2Text:
    """
    Build a `HTML2Text` text maker object with 
    specified configurations.
    """
    text_maker = HTML2Text()
    text_maker.ignore_images = True         # drop <img>; remove [image: image.png] noise
    text_maker.body_width = 0
    text_maker.protect_links = True         # don't break long URLs across lines
    text_maker.ignore_emphasis = False      # keep **bold** / *italic* — carries intent for LLMs
    text_maker.skip_internal_links = True   # drop in-page #anchor links
    text_maker.ignore_tables = True         # ignore table-related tags (table, th, td, tr) while keeping rows
    return text_maker


# Module-level singleton
_TEXT_MAKER = _build_text_maker()

def _clean_plain_text(text: str) -> str:
    """
    Normalize line endings and collapse blank-line runs
    """
    text = text.replace('\r\n', '\n')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def convert(html: str) -> str:
    """
    Convert HTML text to markdown format.
    """

    if not html:
        return ""
    
    markdown = _TEXT_MAKER.handle(html)
    return _clean_plain_text(markdown)
