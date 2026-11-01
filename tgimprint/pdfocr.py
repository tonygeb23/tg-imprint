"""Text recognition for a page that has no text, or text that reads as
nonsense. Local: nothing leaves the machine and no key is needed.

    available(language="eng") -> bool
    page_dict(page, language="eng", dpi=OCR_DPI) -> a get_text("dict") value
    language_for(lang) -> the Tesseract language for a document language
    guess_language(text) -> "es" or "en" or ""

PyMuPDF carries Tesseract inside it, and needs only the language data
(measured 2026-11-01: 0.3 seconds a page at 300 dots per inch, every word of
a skewed noisy test scan right). The data is tessdata_fast from the
Tesseract project, Apache 2.0, in assets/tessdata: English and Spanish, six
megabytes between them, and they never change between releases, so an update
does not carry them again.

A language with no data here simply is not offered; the caller then keeps
today's sentence about pictures of text.

Nothing here touches wx or prints.
"""

import os
import re

import fitz  # PyMuPDF

from . import paths

OCR_DPI = 300

_SPANISH = frozenset(("el", "la", "los", "las", "de", "del", "que", "y", "en", "un", "una",
                      "por", "con", "para", "es", "se", "su", "al", "como", "pero"))
_ENGLISH = frozenset(("the", "of", "and", "to", "in", "a", "is", "that", "for", "it", "on",
                      "with", "as", "was", "be", "by", "this", "are", "from", "at"))


def data_folder():
    return paths.tessdata_dir()


def available(language="eng"):
    folder = data_folder()
    return bool(folder) and all(
        os.path.isfile(os.path.join(folder, part + ".traineddata")) for part in language.split("+"))


def language_for(lang):
    """Spanish for a Spanish document, English for everything else that has
    data. The document's own language decides, not a guess, when it has one."""
    if (lang or "").lower().startswith("es") and available("spa"):
        return "spa"
    return "eng"


def guess_language(text):
    """"es", "en" or "" from the commonest words, for a file that does not
    say. It only ever picks between the two languages we have data for."""
    words = re.findall(r"[^\W\d_]+", text.lower())[:4000]
    if len(words) < 20:
        return ""
    spanish = sum(1 for w in words if w in _SPANISH)
    english = sum(1 for w in words if w in _ENGLISH)
    if max(spanish, english) < len(words) * 0.08:
        return ""
    return "es" if spanish > english else "en"


def _tidy(data):
    """Recognised spans come back with runs of spaces, and with sizes that
    wander by a point from line to line. Space is collapsed here; sizes are
    the caller's, who can see the whole document."""
    for block in data.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span["text"] = re.sub(r"\s+", " ", span.get("text", ""))
                span["flags"] = 0
    return data


def page_dict(page, language="eng", dpi=OCR_DPI):
    """The page read by recognition, in the shape of get_text("dict"). Blocks
    only; the picture the words came from is the caller's to keep or drop."""
    textpage = page.get_textpage_ocr(flags=fitz.TEXT_PRESERVE_WHITESPACE, language=language,
                                     dpi=dpi, full=True, tessdata=data_folder())
    return _tidy(page.get_text("dict", textpage=textpage))
