"""
Editor component — native Windows RICHEDIT50W via wx.TextCtrl(TE_RICH2).

NVDA compatibility
------------------
RICHEDIT50W implements IAccessible/MSAA natively.  Arrow-key navigation,
read-all (NVDA+Down), and character/word reading all work out of the box.
NVDA+F at the caret announces font name, size, bold, italic, etc.
Bullet prefixes (•) and number prefixes (1.) are read as ordinary text.
Image placeholder lines are read as their alt text.
Hyperlinks are styled blue/underlined; NVDA reads the display text.

Key-event ownership
-------------------
Formatting shortcuts (Ctrl+B etc.) are handled EXCLUSIVELY in
_on_key_down by NOT calling event.Skip() for those keys.  This prevents
RICHEDIT from seeing them (which would double-fire or toggle back) AND
prevents the frame's accelerator table from firing a second time.

The accelerator table in MainWindow keeps those entries solely so the
menu items display their shortcut hints — the accelerator paths are
effectively dead code when focus is in the editor.

Enter key
---------
All Enter/newline insertion is done explicitly with WriteText("\n").
We never rely on event.Skip() to let RICHEDIT insert the newline, because
the native RICHEDIT Enter path conflicts with our EVT_KEY_DOWN binding.

Formatting preservation
-----------------------
Every toggle_* and apply_* method reads the existing wx.TextAttr at the
target position first, modifies only the relevant attribute, then writes
the attr back — bold/italic/underline/alignment/size never clobber each
other.

Hyperlinks
----------
insert_link() styles display text as blue + underlined and stores
{display_text, url} in self._links.  At export time rtc_parser detects
the link colour (RGB 0, 0, 180) and looks up the URL.
"""
from __future__ import annotations

import os
import re
import wx

# Public constant used by rtc_parser to recognise image placeholder lines
IMAGE_MARKER_PREFIX = "\U0001F4F7 "   # "📷 "

# Bullet character (Unicode bullet U+2022)
_BULLET = "•"

# Regexes
_BULLET_RE   = re.compile(r"^•\s")
_NUMBERED_RE = re.compile(r"^(\d+)\.\s")

# Hyperlink colour — used as the visual marker for link runs in the TextCtrl.
# rtc_parser checks for exactly these RGB values when building Run objects.
_LINK_COLOR_RGB = (0, 0, 180)   # standard accessible blue


# -----------------------------------------------------------------------
# Style configuration
# -----------------------------------------------------------------------
_STYLE_CFG: dict[str, tuple[int, bool, bool, int]] = {
    "Heading 1":     (28, True,  False,   0),
    "Heading 2":     (22, True,  False,   0),
    "Heading 3":     (18, True,  False,   0),
    "Heading 4":     (16, True,  False,   0),
    "Heading 5":     (14, True,  False,   0),
    "Heading 6":     (13, True,  False,   0),
    "Normal":        (11, False, False,   0),
    "Block Quote":   (11, False, True,  200),
    "Bullet List":   (11, False, False,   0),
    "Numbered List": (11, False, False,   0),
}

_HEADING_STYLES = {f"Heading {i}" for i in range(1, 7)}


def _preferred_face() -> str:
    faces = wx.FontEnumerator.GetFacenames()
    for f in ("Calibri", "Segoe UI", "Arial"):
        if f in faces:
            return f
    return ""


def _make_attr(style_name: str) -> wx.TextAttr:
    pt, bold, italic, indent = _STYLE_CFG[style_name]
    font = wx.Font(
        pt,
        wx.FONTFAMILY_DEFAULT,
        wx.FONTSTYLE_ITALIC  if italic else wx.FONTSTYLE_NORMAL,
        wx.FONTWEIGHT_BOLD   if bold   else wx.FONTWEIGHT_NORMAL,
        faceName=_preferred_face(),
    )
    attr = wx.TextAttr(wx.BLACK, wx.WHITE, font)
    attr.SetLeftIndent(indent)
    attr.SetFontPointSize(pt)
    attr.SetFontWeight(wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL)
    attr.SetFontStyle(wx.FONTSTYLE_ITALIC if italic else wx.FONTSTYLE_NORMAL)
    return attr


# -----------------------------------------------------------------------
# Alignment helpers (shared with rtc_parser / toolbar)
# -----------------------------------------------------------------------

def _align_wx_to_str(wx_align: int) -> str:
    if wx_align == wx.TEXT_ALIGNMENT_CENTRE:
        return "center"
    if wx_align == wx.TEXT_ALIGNMENT_RIGHT:
        return "right"
    if wx_align == wx.TEXT_ALIGNMENT_JUSTIFIED:
        return "justify"
    return "left"


def _align_str_to_wx(align: str) -> int:
    return {
        "center":  wx.TEXT_ALIGNMENT_CENTRE,
        "right":   wx.TEXT_ALIGNMENT_RIGHT,
        "justify": wx.TEXT_ALIGNMENT_JUSTIFIED,
    }.get(align, wx.TEXT_ALIGNMENT_LEFT)


# -----------------------------------------------------------------------
# Editor
# -----------------------------------------------------------------------

class Editor(wx.Panel):
    """
    Accessible rich-text editor panel backed by RICHEDIT50W (WordPad-class).
    NVDA reads it natively via MSAA with no extra work required.
    """

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self.ctrl = wx.TextCtrl(
            self,
            style=wx.TE_MULTILINE | wx.TE_RICH2 | wx.TE_NOHIDESEL,
        )
        self.ctrl.SetName("Document editor")

        faces = wx.FontEnumerator.GetFacenames()
        face  = next((f for f in ("Calibri", "Segoe UI", "Arial") if f in faces), "")
        self.ctrl.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT,
                                  wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL,
                                  faceName=face))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.ctrl, 1, wx.EXPAND)
        self.SetSizer(sizer)

        self._images: list[dict] = []
        self._links:  list[dict] = []   # [{display_text, url}, ...]
        self._current_style = "Normal"

        self.ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.ctrl.Bind(wx.EVT_LEFT_UP,  self._sync_current_style)
        self.ctrl.Bind(wx.EVT_KEY_UP,   self._sync_current_style)

    # ------------------------------------------------------------------
    # Paragraph styles
    # ------------------------------------------------------------------

    def apply_paragraph_style(self, style_name: str) -> None:
        if style_name not in _STYLE_CFG:
            return

        # Operate on every line touched by the current selection — or the
        # caret line if nothing is selected.
        sel_s, sel_e = self.ctrl.GetSelection()
        if sel_s != sel_e:
            ln_first = self.ctrl.GetLineNumberFromPosition(sel_s)
            ln_last  = self.ctrl.GetLineNumberFromPosition(max(sel_s, sel_e - 1))
        else:
            ip = self.ctrl.GetInsertionPoint()
            ln_first = ln_last = self.ctrl.GetLineNumberFromPosition(ip)

        attr = _make_attr(style_name)

        # Walk lines in reverse so earlier offsets stay valid as we rewrite.
        for ln in range(ln_last, ln_first - 1, -1):
            start = self.ctrl.XYToPosition(0, ln)
            raw   = self.ctrl.GetLineText(ln)
            end   = start + len(raw)
            stripped = _strip_list_prefix(raw)

            if style_name == "Bullet List":
                new_raw = f"{_BULLET} " + stripped
            elif style_name == "Numbered List":
                n       = self._list_number_for(ln)
                new_raw = f"{n}. " + stripped
            else:
                new_raw = stripped

            if new_raw != raw:
                self.ctrl.Remove(start, end)
                self.ctrl.SetInsertionPoint(start)
                self.ctrl.WriteText(new_raw)
                end = start + len(new_raw)

            if start < end:
                self.ctrl.SetStyle(start, end, attr)

        self.ctrl.SetDefaultStyle(attr)
        self._current_style = style_name
        self.ctrl.SetFocus()

    def current_paragraph_style(self) -> str:
        ip = self.ctrl.GetInsertionPoint()
        ln = self.ctrl.GetLineNumberFromPosition(ip)
        return self._style_for_line(ln)

    def _style_for_line(self, ln: int) -> str:
        text  = self.ctrl.GetLineText(ln)
        start = self.ctrl.XYToPosition(0, ln)

        if _BULLET_RE.match(text):
            return "Bullet List"
        if _NUMBERED_RE.match(text):
            return "Numbered List"

        attr = wx.TextAttr()
        if self.ctrl.GetStyle(start, attr):
            pt     = attr.GetFontPointSize() or 11
            bold   = attr.GetFontWeight() == wx.FONTWEIGHT_BOLD
            italic = attr.GetFontStyle()  == wx.FONTSTYLE_ITALIC
            indent = attr.GetLeftIndent() or 0

            if italic and indent >= 150:
                return "Block Quote"
            if bold:
                if pt >= 26: return "Heading 1"
                if pt >= 20: return "Heading 2"
                if pt >= 17: return "Heading 3"
                if pt >= 15: return "Heading 4"
                if pt >= 13: return "Heading 5"
                if pt >= 12: return "Heading 6"

        return "Normal"

    def _sync_current_style(self, event: wx.Event) -> None:
        self._current_style = self.current_paragraph_style()
        event.Skip()

    def _list_number_for(self, ln: int) -> int:
        n = 1
        for i in range(ln - 1, -1, -1):
            t = self.ctrl.GetLineText(i)
            if _NUMBERED_RE.match(t):
                n += 1
            elif t.strip():
                break
        return n

    # ------------------------------------------------------------------
    # Character formatting — read-modify-write so nothing is clobbered
    # ------------------------------------------------------------------

    def toggle_bold(self) -> None:
        s, e = self._effective_range()
        attr = wx.TextAttr()
        self.ctrl.GetStyle(s, attr)
        is_bold = attr.GetFontWeight() == wx.FONTWEIGHT_BOLD
        attr.SetFontWeight(wx.FONTWEIGHT_NORMAL if is_bold else wx.FONTWEIGHT_BOLD)
        self.ctrl.SetStyle(s, e, attr)
        self.ctrl.SetDefaultStyle(attr)
        self.ctrl.SetFocus()

    def toggle_italic(self) -> None:
        s, e = self._effective_range()
        attr = wx.TextAttr()
        self.ctrl.GetStyle(s, attr)
        is_italic = attr.GetFontStyle() == wx.FONTSTYLE_ITALIC
        attr.SetFontStyle(wx.FONTSTYLE_NORMAL if is_italic else wx.FONTSTYLE_ITALIC)
        self.ctrl.SetStyle(s, e, attr)
        self.ctrl.SetDefaultStyle(attr)
        self.ctrl.SetFocus()

    def toggle_underline(self) -> None:
        s, e = self._effective_range()
        attr = wx.TextAttr()
        self.ctrl.GetStyle(s, attr)
        attr.SetFontUnderlined(not attr.GetFontUnderlined())
        self.ctrl.SetStyle(s, e, attr)
        self.ctrl.SetDefaultStyle(attr)
        self.ctrl.SetFocus()

    def toggle_strikethrough(self) -> None:
        s, e = self._effective_range()
        attr = wx.TextAttr()
        self.ctrl.GetStyle(s, attr)
        try:
            attr.SetFontStrikethrough(not attr.GetFontStrikethrough())
        except AttributeError:
            return
        self.ctrl.SetStyle(s, e, attr)
        self.ctrl.SetDefaultStyle(attr)
        self.ctrl.SetFocus()

    def _effective_range(self) -> tuple[int, int]:
        s, e = self.ctrl.GetSelection()
        if s != e:
            return s, e
        ip   = self.ctrl.GetInsertionPoint()
        text = self.ctrl.GetValue()
        lo   = ip
        while lo > 0 and text[lo - 1] not in (" ", "\n", "\t"):
            lo -= 1
        hi = ip
        while hi < len(text) and text[hi] not in (" ", "\n", "\t"):
            hi += 1
        return (lo, hi) if lo != hi else (ip, min(ip + 1, len(text)))

    # ------------------------------------------------------------------
    # Paragraph alignment
    # ------------------------------------------------------------------

    def apply_alignment(self, alignment: str) -> None:
        wx_align = _align_str_to_wx(alignment)
        ip    = self.ctrl.GetInsertionPoint()
        ln    = self.ctrl.GetLineNumberFromPosition(ip)
        start = self.ctrl.XYToPosition(0, ln)
        raw   = self.ctrl.GetLineText(ln)
        end   = start + len(raw)

        attr = wx.TextAttr()
        self.ctrl.GetStyle(start if start < end else ip, attr)
        attr.SetAlignment(wx_align)
        if start < end:
            self.ctrl.SetStyle(start, end, attr)
        self.ctrl.SetDefaultStyle(attr)
        self.ctrl.SetFocus()

    def current_alignment(self) -> str:
        ip   = self.ctrl.GetInsertionPoint()
        attr = wx.TextAttr()
        if self.ctrl.GetStyle(ip, attr):
            return _align_wx_to_str(attr.GetAlignment())
        return "left"

    # ------------------------------------------------------------------
    # Hyperlink insertion
    # ------------------------------------------------------------------

    def insert_link(self, display_text: str, url: str) -> None:
        """
        Insert *display_text* styled as a hyperlink (blue + underline).

        The URL is stored in self._links and recovered at parse time by
        matching the display_text against known entries.

        NVDA reads the display text as plain text; the link is announced
        as a clickable hyperlink in the exported PDF.
        """
        if not display_text or not url:
            return

        ip = self.ctrl.GetInsertionPoint()
        s, e = self.ctrl.GetSelection()

        # If text is selected, replace it; otherwise insert at caret
        if s != e:
            self.ctrl.Remove(s, e)
            self.ctrl.SetInsertionPoint(s)
            ip = s

        start = self.ctrl.GetInsertionPoint()
        self.ctrl.WriteText(display_text)
        end = self.ctrl.GetInsertionPoint()

        # Style: blue + underlined (preserve font size / family)
        attr = wx.TextAttr()
        self.ctrl.GetStyle(start, attr)
        attr.SetTextColour(wx.Colour(*_LINK_COLOR_RGB))
        attr.SetFontUnderlined(True)
        self.ctrl.SetStyle(start, end, attr)

        # Reset default style back to non-link so next typed text isn't a link
        plain = wx.TextAttr()
        self.ctrl.GetStyle(end, plain)
        plain.SetTextColour(wx.NullColour)
        plain.SetFontUnderlined(False)
        self.ctrl.SetDefaultStyle(plain)

        self._links.append({"display_text": display_text, "url": url})
        self.ctrl.SetFocus()

    def get_links(self) -> list[dict]:
        return self._links

    # ------------------------------------------------------------------
    # Image insertion
    # ------------------------------------------------------------------

    def insert_image(self, path: str, alt_text: str) -> None:
        if alt_text:
            marker = IMAGE_MARKER_PREFIX + alt_text
        else:
            marker = IMAGE_MARKER_PREFIX + f"[Decorative: {os.path.basename(path)}]"

        ip   = self.ctrl.GetInsertionPoint()
        text = self.ctrl.GetValue()

        prefix = "\n" if ip > 0 and text[ip - 1:ip] != "\n" else ""
        self.ctrl.SetInsertionPoint(ip)
        self.ctrl.WriteText(prefix + marker + "\n")

        ln    = self.ctrl.GetLineNumberFromPosition(ip + len(prefix))
        s     = self.ctrl.XYToPosition(0, ln)
        e     = s + len(marker)
        attr  = wx.TextAttr(wx.Colour(90, 90, 90), wx.NullColour,
                             wx.Font(10, wx.FONTFAMILY_DEFAULT,
                                     wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        self.ctrl.SetStyle(s, e, attr)
        self._images.append({"marker": marker, "path": path, "alt_text": alt_text})
        self.ctrl.SetFocus()

    def get_images(self) -> list[dict]:
        return self._images

    # ------------------------------------------------------------------
    # Keyboard handling
    # ------------------------------------------------------------------

    def _on_key_down(self, event: wx.KeyEvent) -> None:
        """
        Central key handler.

        Formatting shortcuts are consumed here (no event.Skip) so that
        RICHEDIT never sees them — preventing both native double-handling
        and the accelerator table from firing a second time.

        ALL newline insertion is done explicitly with WriteText("\n") so
        we never depend on RICHEDIT's native Enter handling, which can
        conflict with this EVT_KEY_DOWN binding.
        """
        key   = event.GetKeyCode()
        ctrl  = event.ControlDown()
        shift = event.ShiftDown()
        alt   = event.AltDown()

        # ---- Ctrl+Alt shortcuts (paragraph styles) ------------------------
        # Handled here, not via accelerator table, because RICHEDIT50W
        # intercepts Ctrl+Alt+digit on Windows (AltGr-equivalent).
        if ctrl and alt and not shift:
            if ord("1") <= key <= ord("6"):
                self.apply_paragraph_style(f"Heading {key - ord('0')}")
                return
            if key == ord("0"):
                self.apply_paragraph_style("Normal")
                return
            if key == ord("8"):
                self.apply_paragraph_style("Bullet List")
                return
            if key == ord("9"):
                self.apply_paragraph_style("Numbered List")
                return

        # ---- Ctrl shortcuts -----------------------------------------------
        if ctrl and not alt:
            if shift:
                if key == ord("I"):
                    self.toggle_italic()
                    return                  # consume — RICHEDIT must not see it
                if key == ord("K"):
                    self.toggle_strikethrough()
                    return
                # Ctrl+Shift+F / Ctrl+Shift+E handled by accelerator table → main_window
            else:
                if key == ord("B"):
                    self.toggle_bold()
                    return
                if key == ord("U"):
                    self.toggle_underline()
                    return
                if key == ord("L"):
                    self.apply_alignment("left")
                    return
                if key == ord("E"):
                    self.apply_alignment("center")
                    return
                if key == ord("R"):
                    self.apply_alignment("right")
                    return
                if key == ord("J"):
                    self.apply_alignment("justify")
                    return
                if key == ord("Q"):
                    self.apply_paragraph_style("Block Quote")
                    return
                # Ctrl+K / Ctrl+F / Ctrl+H / Ctrl+I → let accelerator table handle

        # ---- Enter / newline ----------------------------------------------
        if key == wx.WXK_RETURN and not ctrl and not alt:
            if shift:
                self.ctrl.WriteText("\n")
                return

            ip = self.ctrl.GetInsertionPoint()
            ln = self.ctrl.GetLineNumberFromPosition(ip)
            if self._try_smart_return(ln, ip):
                return          # list / block-quote continuation handled

            # Plain Enter — explicit insert (Skip() is unreliable on
            # RICHEDIT through wx on Windows; some configurations drop the
            # WM_CHAR translation and the newline never lands).
            was_heading = self._current_style in _HEADING_STYLES
            self.ctrl.WriteText("\n")
            # Move caret explicitly so NVDA receives a caret-moved event
            # for the new line position.
            new_ip = self.ctrl.GetInsertionPoint()
            self.ctrl.SetInsertionPoint(new_ip)
            if was_heading:
                wx.CallAfter(self._after_plain_return)
            return

        event.Skip()

    def _try_smart_return(self, ln: int, ip: int) -> bool:
        text  = self.ctrl.GetLineText(ln)
        start = self.ctrl.XYToPosition(0, ln)
        end   = start + len(text)

        # Empty bullet → exit list
        if text.strip() == _BULLET:
            self.ctrl.Remove(start, end)
            self.ctrl.SetInsertionPoint(start)
            wx.CallAfter(self.apply_paragraph_style, "Normal")
            return True

        # Empty numbered item → exit list
        if _NUMBERED_RE.match(text) and not _NUMBERED_RE.sub("", text).strip():
            self.ctrl.Remove(start, end)
            self.ctrl.SetInsertionPoint(start)
            wx.CallAfter(self.apply_paragraph_style, "Normal")
            return True

        # Bullet continuation
        if _BULLET_RE.match(text):
            attr = wx.TextAttr()
            self.ctrl.GetStyle(start, attr)
            self.ctrl.SetInsertionPoint(self.ctrl.XYToPosition(0, ln) + len(text))
            self.ctrl.WriteText(f"\n{_BULLET} ")
            new_ln    = self.ctrl.GetLineNumberFromPosition(self.ctrl.GetInsertionPoint())
            new_start = self.ctrl.XYToPosition(0, new_ln)
            self.ctrl.SetStyle(new_start, new_start + 2, attr)
            return True

        # Numbered list continuation
        m = _NUMBERED_RE.match(text)
        if m:
            attr = wx.TextAttr()
            self.ctrl.GetStyle(start, attr)
            nxt    = int(m.group(1)) + 1
            prefix = f"{nxt}. "
            self.ctrl.SetInsertionPoint(start + len(text))
            self.ctrl.WriteText(f"\n{prefix}")
            new_ln    = self.ctrl.GetLineNumberFromPosition(self.ctrl.GetInsertionPoint())
            new_start = self.ctrl.XYToPosition(0, new_ln)
            self.ctrl.SetStyle(new_start, new_start + len(prefix), attr)
            return True

        # Block quote continuation
        attr = wx.TextAttr()
        self.ctrl.GetStyle(start, attr)
        if (attr.GetFontStyle() == wx.FONTSTYLE_ITALIC
                and (attr.GetLeftIndent() or 0) >= 150):
            self.ctrl.SetInsertionPoint(start + len(text))
            self.ctrl.WriteText("\n")
            new_ln    = self.ctrl.GetLineNumberFromPosition(self.ctrl.GetInsertionPoint())
            new_start = self.ctrl.XYToPosition(0, new_ln)
            self.ctrl.SetStyle(new_start, new_start + 1, attr)
            self.ctrl.SetDefaultStyle(attr)
            return True

        return False

    def _after_plain_return(self) -> None:
        """After Enter on a heading, reset the new line to Normal style."""
        if self._current_style in _HEADING_STYLES:
            self.apply_paragraph_style("Normal")

    # ------------------------------------------------------------------
    # Heading navigation  (F6 / Shift+F6)
    # ------------------------------------------------------------------

    def go_to_next_heading(self) -> str | None:
        return self._heading_search(forward=True)

    def go_to_prev_heading(self) -> str | None:
        return self._heading_search(forward=False)

    def _heading_search(self, forward: bool) -> str | None:
        ip  = self.ctrl.GetInsertionPoint()
        cur = self.ctrl.GetLineNumberFromPosition(ip)
        n   = self.ctrl.GetNumberOfLines()

        line_range = range(cur + 1, n) if forward else range(cur - 1, -1, -1)
        for ln in line_range:
            style = self._style_for_line(ln)
            if style.startswith("Heading"):
                pos = self.ctrl.XYToPosition(0, ln)
                self.ctrl.SetInsertionPoint(pos)
                self.ctrl.ShowPosition(pos)
                self.ctrl.SetFocus()
                self._current_style = style
                return style
        return None

    def heading_positions(self) -> list[tuple[int, int, str]]:
        results = []
        n = self.ctrl.GetNumberOfLines()
        for ln in range(n):
            style = self._style_for_line(ln)
            if style.startswith("Heading"):
                pos = self.ctrl.XYToPosition(0, ln)
                results.append((ln, pos, style))
        return results

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def save(self, path: str) -> None:
        self.ctrl.SaveFile(path, wx.TEXT_TYPE_RTF)

    def load(self, path: str) -> None:
        self.ctrl.LoadFile(path, wx.TEXT_TYPE_RTF)
        self._images.clear()
        self._links.clear()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def clear(self) -> None:
        self.ctrl.Clear()
        self._images.clear()
        self._links.clear()
        self._current_style = "Normal"

    def word_count(self) -> int:
        t = self.ctrl.GetValue()
        return len(t.split()) if t.strip() else 0

    def Bind(self, event, handler, source=None, **kwargs):
        if event == wx.EVT_TEXT:
            self.ctrl.Bind(wx.EVT_TEXT, handler)
        else:
            super().Bind(event, handler, source=source, **kwargs)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _strip_list_prefix(text: str) -> str:
    if _BULLET_RE.match(text):
        return text[2:]
    m = _NUMBERED_RE.match(text)
    if m:
        return text[m.end():]
    return text
