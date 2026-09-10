"""The editor page: the HTML, CSS and JavaScript inside the WebView2.

One contenteditable region that only ever holds semantic markup, a key map
generated from tgimprint/ui/keymap.py, and a message bridge to Python.

Three measured facts shape it (CLAUDE.md, CHALLENGE.md W2, W4 to W7, W11):

- With the WebView2 focused no wx accelerator fires and the page sees every
  key, so the whole keyboard contract lives here, in a capture phase keydown
  handler that calls preventDefault for every bound key and forwards the
  app's keys to Python with postMessage. F5, Ctrl+F, Ctrl+P and the other
  browser keys never reach Chromium's defaults.
- Every programmatic edit goes through execCommand (insertHTML, insertText,
  delete) so the browser's undo stack sees it. A range.insertNode edit is
  invisible to undo and Ctrl+Z after it removes the user's own typing.
- Only sanitised HTML enters the page (Python runs htmlclean.normalise
  before every load and paste), and the page carries a Content Security
  Policy with a per load nonce, so an inline handler in a received file
  cannot run even if the sanitiser missed it.

The page never talks to the network: img-src is data: only and every
navigation after the first load is vetoed by the wrapper.
"""
import json
import secrets

from . import constants as C
from . import settings as settings_mod

#: Widths of the page, in CSS units, for the paper on screen.
PAGE_DIMENSIONS = {
    "letter": ("8.5in", "11in"),
    "A4": ("210mm", "297mm"),
    "legal": ("8.5in", "14in"),
}

_CSS = """
/* Every colour, the caret, the focus ring, the weight and the line spacing
   are custom properties, so the Display page changes them by writing one
   variable on the html element and never touches the text. The exported PDF
   is built from the body HTML alone, so no screen theme can reach it;
   tests/test_display.py proves that. */
:root {
  --surround: #e3e6eb; --paper: #ffffff; --ink: #111111; --muted: #444444;
  --rule: #8f96a3; --soft: #c8ccd4; --panel: #f1f3f6; --panel-ink: #111111;
  --link: #0b4fb8; --focus: #2b6fd6; --sel: #b9d3ff; --sel-ink: #111111;
  --caret: #000000; --caret-width: 2px; --focus-width: 3px;
  --body-weight: normal; --line-height: 1.5;
  --shadow: 0 1px 2px rgba(0,0,0,0.20), 0 6px 20px rgba(0,0,0,0.12);
  color-scheme: light;
}
html[data-theme="dark"] {
  --surround: #16181c; --paper: #1e2126; --ink: #eef1f6; --muted: #c3c9d4;
  --rule: #6f7783; --soft: #3a4049; --panel: #2a2e35; --panel-ink: #eef1f6;
  --link: #86b8ff; --focus: #7ab4ff; --sel: #2f5c9e; --sel-ink: #ffffff;
  --caret: #ffffff; --shadow: none;
  color-scheme: dark;
}
html[data-theme="yellow_on_black"] {
  --surround: #000000; --paper: #000000; --ink: #ffff00; --muted: #ffff00;
  --rule: #ffff00; --soft: #ffff00; --panel: #000000; --panel-ink: #ffff00;
  --link: #66d9ff; --focus: #ffff00; --sel: #ffff00; --sel-ink: #000000;
  --caret: #ffff00; --shadow: none;
  color-scheme: dark;
}
/* Follow Windows: the system colour keywords, and the light or dark the
   system asks for. When Windows really is in a high contrast mode every
   theme collapses to the forced-colors block at the foot of this sheet. */
html[data-theme="high_contrast"] {
  --surround: Canvas; --paper: Canvas; --ink: CanvasText; --muted: CanvasText;
  --rule: CanvasText; --soft: CanvasText; --panel: Canvas; --panel-ink: CanvasText;
  --link: LinkText; --focus: Highlight; --sel: Highlight; --sel-ink: HighlightText;
  --caret: CanvasText; --shadow: none;
  color-scheme: light dark;
}
html, body { margin: 0; padding: 0; background: var(--surround); }
body { font-family: %(font)s; font-size: %(px)spx; line-height: var(--line-height); }
#editor {
  box-sizing: border-box;
  background: var(--paper); color: var(--ink); font-weight: var(--body-weight);
  width: %(width)s; max-width: calc(100vw - 32px); min-height: %(height)s;
  margin: 16px auto 32px auto; padding: %(margin)s;
  box-shadow: var(--shadow);
  border: 1px solid var(--soft); border-radius: 2px;
  outline: none; caret-color: var(--caret);
  overflow-wrap: break-word;
}
#editor:focus { box-shadow: 0 0 0 var(--focus-width) var(--focus), var(--shadow);
  border-color: var(--focus); }
/* The caret the Display page can widen. The browser draws a one pixel bar,
   which disappears against a large font; this one is a box of the asked for
   width, sitting over the native caret, which is hidden only while it runs.
   It is outside #editor, so it is not part of the document. */
#tgcaret { position: fixed; display: none; background: var(--caret);
  width: 2px; pointer-events: none; z-index: 5;
  animation: tgblink 1.06s steps(1) infinite; }
html[data-fatcaret="1"] #editor { caret-color: transparent; }
@keyframes tgblink { 0%%, 49%% { opacity: 1; } 50%%, 100%% { opacity: 0; } }
#editor h1 { font-size: 2.0em; margin: 0.8em 0 0.35em; line-height: 1.2; }
#editor h2 { font-size: 1.6em; margin: 0.8em 0 0.35em; line-height: 1.25; }
#editor h3 { font-size: 1.3em; margin: 0.8em 0 0.3em; line-height: 1.3; }
#editor h4 { font-size: 1.15em; margin: 0.7em 0 0.3em; }
#editor h5 { font-size: 1.05em; margin: 0.6em 0 0.25em; }
#editor h6 { font-size: 1.0em; margin: 0.6em 0 0.25em; font-style: italic; }
#editor p { margin: 0 0 0.7em; }
#editor ul, #editor ol { margin: 0 0 0.7em; padding-left: 2.2em; }
#editor li { margin: 0 0 0.2em; }
#editor a { color: var(--link); text-decoration: underline; }
#editor blockquote { margin: 0.6em 0 0.8em 1.6em; padding: 0.1em 0 0.1em 1em;
  border-left: 4px solid var(--rule); color: var(--muted); }
#editor blockquote p:last-child { margin-bottom: 0; }
#editor code { font-family: Consolas, "Courier New", monospace; font-size: 0.95em;
  background: var(--panel); color: var(--panel-ink); padding: 0 0.2em; border-radius: 2px; }
#editor p.code-block { font-family: Consolas, "Courier New", monospace; white-space: pre-wrap;
  background: var(--panel); color: var(--panel-ink); padding: 0.5em 0.7em; }
#editor figure { display: block; margin: 0.8em 0; padding: 0; max-width: 100%%; }
#editor figure img { display: block; width: 100%%; height: auto; }
#editor figcaption { font-size: 0.9em; color: var(--muted); margin-top: 0.35em; }
#editor figure.width-quarter { width: 25%%; }
#editor figure.width-half { width: 50%%; }
#editor figure.width-three-quarters { width: 75%%; }
#editor figure.width-full { width: 100%%; }
#editor figure.place-left { margin-right: auto; }
#editor figure.place-centre { margin-left: auto; margin-right: auto; }
#editor figure.place-right { margin-left: auto; }
#editor figure.imprint-here { outline: var(--focus-width) dashed var(--focus); outline-offset: 3px; }
#editor table { border-collapse: collapse; margin: 0.6em 0 0.9em; width: 100%%; }
#editor th, #editor td { border: 1px solid var(--rule); padding: 0.3em 0.5em; text-align: left;
  vertical-align: top; min-width: 2em; }
#editor th { background: var(--panel); color: var(--panel-ink); font-weight: bold; }
#editor .align-left { text-align: left; }
#editor .align-center { text-align: center; }
#editor .align-right { text-align: right; }
#editor .align-justify { text-align: justify; }
#editor hr { border: 0; border-top: 1px solid var(--rule); margin: 1em 0; }
::selection { background: var(--sel); color: var(--sel-ink); }
/* Windows high contrast wins over every theme, and nothing here fights it:
   the variables are remapped to the system colours, so the page is drawn in
   the colours the person chose in Windows whatever the Display page says. */
@media (forced-colors: active) {
  :root, html[data-theme] {
    --surround: Canvas; --paper: Canvas; --ink: CanvasText; --muted: CanvasText;
    --rule: CanvasText; --soft: CanvasText; --panel: Canvas; --panel-ink: CanvasText;
    --link: LinkText; --focus: Highlight; --sel: Highlight; --sel-ink: HighlightText;
    --caret: CanvasText; --shadow: none;
  }
  #editor { forced-color-adjust: auto; box-shadow: none; }
  #editor:focus { outline: var(--focus-width) solid Highlight; outline-offset: 2px; box-shadow: none; }
  #tgcaret { background: CanvasText; }
}
"""

_JS = r"""
(function () {
  'use strict';
  var ed = document.getElementById('editor');
  var BIND = __BINDINGS__;
  var DENY = __DENY__;
  var BLOCKS = /^(H[1-6]|P|LI|BLOCKQUOTE|FIGURE|FIGCAPTION|TD|TH|PRE|DIV)$/;
  var ZOOMS = __ZOOMS__;                 // whole percentages, from settings.py
  var SPACING = __SPACING__;
  var display = __DISPLAY__;             // what the settings file says

  function post(obj) {
    var text = JSON.stringify(obj);
    try { window.tgimprint.postMessage(text); return; } catch (e) {}
    try { window.chrome.webview.postMessage(text); } catch (e2) {}
  }

  // ------------------------------------------------------------ the keys --
  var byChord = {}, byCode = {}, deny = {};
  BIND.forEach(function (b) { if (b.code) { byCode[b.chord] = b; } else { byChord[b.chord] = b; } });
  DENY.forEach(function (c) { deny[c] = true; });
  var NAMED = { Enter: 'enter', Delete: 'delete', Tab: 'tab', Escape: 'escape',
    ContextMenu: 'contextmenu', Backspace: 'backspace', ArrowLeft: 'left',
    ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Home: 'home', End: 'end',
    BrowserBack: 'browserback', BrowserForward: 'browserforward',
    BrowserRefresh: 'browserrefresh', BrowserHome: 'browserhome',
    BrowserSearch: 'browsersearch', BrowserFavorites: 'browserfavorites' };

  function physicalDigit(e) {
    var m = /^Digit(\d)$/.exec(e.code || '');
    if (m) { return m[1]; }
    if (e.keyCode >= 48 && e.keyCode <= 57) { return String(e.keyCode - 48); }
    return null;
  }

  function chordOf(e, useCode) {
    var parts = [];
    if (e.ctrlKey) { parts.push('ctrl'); }
    if (e.altKey) { parts.push('alt'); }
    if (e.shiftKey) { parts.push('shift'); }
    var k = e.key || '';
    if (useCode) {
      k = physicalDigit(e);
      if (k === null) { return null; }
    } else if (k.length === 1) {
      k = k.toLowerCase();
      if (k === '+') { k = '='; }
    } else {
      k = NAMED[k] || k.toLowerCase();
    }
    parts.push(k);
    return parts.join('+');
  }

  function bindingFor(e) {
    var b = byChord[chordOf(e, false)];
    if (!b) {
      var cc = chordOf(e, true);
      if (cc && byCode[cc]) { b = byCode[cc]; }
    }
    return b || null;
  }

  document.addEventListener('keydown', function (e) {
    if (e.isComposing) { return; }
    // Any key other than Alt itself means Alt was NOT pressed alone. This
    // has to happen before a binding can return early: Ctrl+Alt+1 applied
    // the heading and then, because the flag was still set from the Alt
    // press, the Alt release opened the menu bar. Tony hit it on
    // 2026-09-09 with Ctrl+Alt+1 to 3; tests/test_altmenu.py measures it.
    if (e.key !== 'Alt') { altAlone = false; }
    var b = bindingFor(e);
    if (b) {
      if (b.scope === 'native') { return; }
      if (b.gate === 'key' && !/^\d$/.test(e.key)) { return; }   // AltGr typed a character
      if (b.conditional && !applies(b.action)) { return; }
      e.preventDefault();
      e.stopPropagation();
      if (b.scope === 'page') { run(b.action); }
      else { post({ type: 'key', action: b.action }); }
      return;
    }
    var c = chordOf(e, false);
    if (deny[c]) { e.preventDefault(); e.stopPropagation(); return; }
    if (e.altKey && !e.ctrlKey && /^[a-z]$/.test(c.slice(-1)) && c === 'alt+' + c.slice(-1)) {
      e.preventDefault(); e.stopPropagation();
      altAlone = false;
      post({ type: 'menu', key: c.slice(-1) });
      return;
    }
    // Shift+F10 is not here: it arrives as a contextmenu event, which the
    // handler above forwards, and the keymap entry for it is native.
    if (c === 'f10') {
      e.preventDefault(); e.stopPropagation();
      post({ type: 'menu', key: '' });
      return;
    }
    if (e.key === 'Alt') { altAlone = true; } else { altAlone = false; }
    if (c === 'backspace' && unlistOnBackspace()) { e.preventDefault(); return; }
    if (c === 'enter' && enterInFigure()) { e.preventDefault(); return; }
  }, true);

  // A lone Alt, pressed and released with nothing in between, opens the
  // menu bar as it does in every other Windows program.
  var altAlone = false;
  document.addEventListener('keyup', function (e) {
    if (e.key === 'Alt' && altAlone) {
      altAlone = false;
      e.preventDefault();
      post({ type: 'menu', key: '' });
    }
  }, true);

  // The Applications key and Shift+F10 arrive here as a contextmenu event
  // with the caret's position; a right click arrives with the mouse's.
  document.addEventListener('contextmenu', function (e) {
    e.preventDefault();
    var x = e.clientX, y = e.clientY;
    var sel = window.getSelection();
    if (sel && sel.rangeCount) {
      var r = sel.getRangeAt(0).getBoundingClientRect();
      if ((!x && !y) || e.button !== 2) {
        if (r && (r.width || r.height || r.left || r.top)) { x = r.left; y = r.bottom; }
        else { var b = (blockOf(sel.anchorNode) || ed).getBoundingClientRect(); x = b.left + 8; y = b.top + 16; }
      }
    }
    post({ type: 'contextmenu', x: Math.round(x), y: Math.round(y) });
  }, true);

  // ------------------------------------------------------- the selection --
  function closest(tag) {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) { return null; }
    var n = sel.anchorNode;
    if (!n) { return null; }
    if (n.nodeType !== 1) { n = n.parentElement; }
    if (!n || !ed.contains(n)) { return null; }
    var found = n.closest(tag);
    return (found && ed.contains(found) && found !== ed) ? found : null;
  }

  function blockOf(node) {
    var n = node && node.nodeType === 1 ? node : (node && node.parentElement);
    while (n && n !== ed && !BLOCKS.test(n.tagName)) { n = n.parentElement; }
    return (n && n !== ed) ? n : null;
  }

  function alignOf(block) {
    if (!block) { return 'left'; }
    var cls = block.className || '';
    if (/align-center/.test(cls)) { return 'center'; }
    if (/align-right/.test(cls)) { return 'right'; }
    if (/align-justify/.test(cls)) { return 'justify'; }
    var a = (block.style.textAlign || getComputedStyle(block).textAlign || 'left').toLowerCase();
    if (a.indexOf('center') === 0) { return 'center'; }
    if (a.indexOf('right') === 0) { return 'right'; }
    if (a.indexOf('justify') === 0) { return 'justify'; }
    return 'left';
  }

  function figures() { return Array.prototype.slice.call(ed.querySelectorAll('figure')); }
  function tables() { return Array.prototype.slice.call(ed.querySelectorAll('table')); }

  function figureInfo(fig) {
    if (!fig) { return null; }
    var img = fig.querySelector('img');
    var cap = fig.querySelector('figcaption');
    var cls = fig.className || '';
    var width = (/width-(quarter|half|three-quarters|full)/.exec(cls) || [0, 'half'])[1];
    var place = (/place-(left|centre|right)/.exec(cls) || [0, 'centre'])[1];
    var alt = img ? (img.getAttribute('alt') || '') : '';
    var decorative = !!img && img.hasAttribute('alt') && alt === '' && !img.hasAttribute('data-needs-alt');
    return { index: figures().indexOf(fig), alt: alt, decorative: decorative,
      caption: cap ? cap.textContent : '', width: width, place: place,
      before: textBefore(fig), heading: headingBefore(fig),
      altSource: img ? (img.getAttribute('data-alt-source') || '') : '',
      needsAlt: !!img && (img.hasAttribute('data-needs-alt') || (!img.hasAttribute('alt'))),
      src: img ? (img.getAttribute('src') || '') : '' };
  }

  // The block in front of a figure, and the heading it sits under: the
  // context a describer needs. Both are read from the document, never
  // written to it.
  function textBefore(node) {
    var n = node && node.previousElementSibling;
    while (n) {
      var text = (n.textContent || '').trim();
      if (text) { return text.slice(-400); }
      n = n.previousElementSibling;
    }
    return '';
  }

  function headingBefore(node) {
    var n = node;
    while (n) {
      if (n.tagName && /^H[1-6]$/.test(n.tagName)) { return (n.textContent || '').trim(); }
      n = n.previousElementSibling;
    }
    return '';
  }

  // Only a figure with the caret inside it counts as "at the caret". The
  // caret lands inside a figure when Up or Down walks onto its line, when
  // Ctrl+Shift+Alt+P or the structure keys jump to it, or when the user is
  // typing in its caption.
  function figureAtCaret() { return closest('figure'); }

  function markCurrentFigure() {
    var fig = closest('figure');
    figures().forEach(function (f) { f.classList.toggle('epdf-here', f === fig); });
  }

  function currentBlockName() {
    var fig = closest('figure');
    if (fig) { return 'figure'; }
    var cell = closest('td,th');
    if (cell) { return cell.tagName.toLowerCase(); }
    var li = closest('li');
    if (li) { var list = li.closest('ol,ul'); return (list && list.tagName === 'OL') ? 'ol' : 'ul'; }
    var sel = window.getSelection();
    var block = sel && sel.rangeCount ? blockOf(sel.anchorNode) : null;
    if (!block) { return 'p'; }
    var t = block.tagName.toLowerCase();
    if (t === 'div' || t === 'pre') { return 'p'; }
    return t;
  }

  function stateObject() {
    var sel = window.getSelection();
    var has = !!(sel && sel.rangeCount && ed.contains(sel.anchorNode));
    var block = has ? blockOf(sel.anchorNode) : null;
    var a = has ? closest('a') : null;
    return { type: 'state',
      block: has ? currentBlockName() : 'p',
      quote: has && !!closest('blockquote'),
      align: alignOf(block || (closest('li') || null)),
      bold: has && document.queryCommandState('bold'),
      italic: has && document.queryCommandState('italic'),
      underline: has && document.queryCommandState('underline'),
      strike: has && document.queryCommandState('strikeThrough'),
      code: has && !!closest('code'),
      link: a ? { text: a.textContent, href: a.getAttribute('href') || '' } : null,
      figure: has ? figureInfo(closest('figure')) : null,
      table: has && !!closest('table'),
      collapsed: !has || sel.isCollapsed,
      focused: document.activeElement === ed };
  }

  var statePending = false;
  function postState() {
    if (statePending) { return; }
    statePending = true;
    setTimeout(function () { statePending = false; markCurrentFigure(); post(stateObject()); }, 40);
  }
  document.addEventListener('selectionchange', postState);

  var wordTimer = null;
  function wordCount() {
    var t = (ed.innerText || '').trim();
    return t ? t.split(/\s+/).length : 0;
  }
  function scheduleWords() {
    if (wordTimer) { clearTimeout(wordTimer); }
    wordTimer = setTimeout(function () { wordTimer = null; post({ type: 'words', count: wordCount() }); }, 500);
  }

  // Bare text typed straight into the host stays a bare text node, which the
  // PDF tags as nothing at all (W8, E5). Wrap it as it happens.
  function wrapBareText() {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) { return; }
    var n = sel.anchorNode;
    if (!n || !ed.contains(n) || n === ed) {
      if (n === ed && ed.childNodes.length) {
        var child = ed.childNodes[Math.min(sel.anchorOffset, ed.childNodes.length - 1)];
        if (child && isLoose(child)) { document.execCommand('formatBlock', false, 'p'); }
      }
      return;
    }
    var top = n;
    while (top.parentNode && top.parentNode !== ed) { top = top.parentNode; }
    if (isLoose(top)) { document.execCommand('formatBlock', false, 'p'); }
  }

  // A top level child of the host that is not a block: bare text, or an
  // inline element such as a strong or a br standing on its own.
  function isLoose(node) {
    if (node.nodeType === 3) { return node.nodeValue.trim() !== ''; }
    if (node.nodeType !== 1) { return false; }
    return !BLOCKS.test(node.tagName) && !/^(UL|OL|TABLE|HR)$/.test(node.tagName);
  }

  ed.addEventListener('input', function () {
    if (!ed.firstChild) { ed.innerHTML = '<p><br></p>'; placeCaret(ed.firstChild, true); }
    wrapBareText();
    post({ type: 'modified' });
    scheduleWords();
    postState();
  });

  // ------------------------------------------------------------ editing --
  function exec(cmd, value) {
    ed.focus();
    return document.execCommand(cmd, false, value === undefined ? null : value);
  }

  function placeCaret(node, atStart) {
    var r = document.createRange();
    r.selectNodeContents(node);
    r.collapse(!!atStart);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }

  function selectNode(node) {
    var r = document.createRange();
    r.selectNode(node);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
  }

  // Lists, all measured on this WebView2 (2026-09-09, probe_lists2):
  //
  // - Chromium's own list toggle on an item of the SAME kind takes the
  //   item out and leaves its text bare between the split halves of the
  //   list ("<ul><li>A</li></ul>Two<br><ul><li>C</li></ul>"), and a
  //   formatBlock straight after wraps that bare text cleanly, as a p or
  //   as a heading. Both steps are execCommand, so undo sees them (two
  //   Ctrl+Z put the item back).
  // - The toggle of the OTHER kind converts the list in place: an ol li
  //   under insertUnorderedList becomes a ul li, at the same level.
  // - insertUnorderedList on a paragraph puts the new list INSIDE the
  //   paragraph ("<p><ul><li>"), which the PDF tags as a paragraph holding
  //   a list; insertHTML over the selected paragraph or paragraphs gives a
  //   clean list in their place and undoes in one step. So a new list is
  //   made by insertHTML, never by the native command.
  // - outdent and formatBlock on a list item both go wrong (outdent leaves
  //   bare text, formatBlock wraps the whole list in the heading), so
  //   neither is used for leaving a list any more.
  function listOf(li) { return li ? li.parentNode : null; }

  function nested(li) {
    var list = listOf(li);
    return !!(list && list.parentNode && list.parentNode !== ed
              && /^(LI|UL|OL)$/.test(list.parentNode.tagName));
  }

  // Whitespace-only text nodes either side of a top level list. They come
  // from the sanitised load and from insertHTML, and Chromium's toggle
  // merges them into the freed item's text ("\nTwo"), which formatBlock
  // keeps and the next insertHTML turns into &nbsp;. Measured: removing
  // them first gives clean text, and undo and redo both still replay
  // correctly (probe_lists6, 2026-09-09).
  function dropBlankNeighbours(list) {
    var top = list;
    while (top && top.parentNode && top.parentNode !== ed) { top = top.parentNode; }
    if (!top || top.parentNode !== ed) { return; }
    ['previousSibling', 'nextSibling'].forEach(function (side) {
      var t = top[side];
      while (t && t.nodeType === 3 && !t.nodeValue.trim()) {
        var next = t[side];
        t.parentNode.removeChild(t);
        t = next;
      }
    });
  }

  // Take the item at the caret out of its list. The text is left bare
  // unless `wrap` is set, because the caller's own formatBlock follows.
  function leaveList(wrap) {
    var guard = 0;
    while (closest('li') && nested(closest('li')) && guard++ < 8) { exec('outdent'); }
    var li = closest('li');
    if (li) {
      dropBlankNeighbours(listOf(li));
      exec(listOf(li).tagName === 'OL' ? 'insertOrderedList' : 'insertUnorderedList');
    }
    if (wrap !== false) { wrapBareText(); }
  }

  function setBlock(tag) {
    var was = currentBlockName();
    if (closest('li')) { leaveList(false); }
    if (closest('blockquote') && tag !== 'blockquote') { exec('outdent'); }
    exec('formatBlock', '<' + tag + '>');
    return { was: was, now: currentBlockName() };
  }

  function topOf(node) {
    var n = node;
    while (n && n.parentNode && n.parentNode !== ed) { n = n.parentNode; }
    return (n && n.parentNode === ed) ? n : null;
  }

  // The top level blocks the selection touches, first to last.
  function selectedTopBlocks() {
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount) { return []; }
    var r = sel.getRangeAt(0);
    var a = topOf(r.startContainer), b = topOf(r.endContainer);
    if (!a) { return []; }
    var out = [], n = a;
    while (n) {
      if (n.nodeType === 1) { out.push(n); }
      if (n === b) { break; }
      n = n.nextSibling;
    }
    return out;
  }

  function toggleList(cmd, wantOrdered) {
    var li = closest('li');
    if (li) {
      var isOrdered = listOf(li).tagName === 'OL';
      if (isOrdered === wantOrdered) { leaveList(true); return { on: false }; }
      exec(cmd);
      return { on: !!closest('li') };
    }
    var block = currentBlockName();
    if (block === 'figure' || block === 'td' || block === 'th') { return { on: false }; }
    if (closest('blockquote')) { exec('outdent'); }
    var blocks = selectedTopBlocks();
    if (blocks.some(function (b) { return /^H[1-6]$/.test(b.tagName); })) {
      exec('formatBlock', '<p>');
      blocks = selectedTopBlocks();
    }
    blocks = blocks.filter(function (b) { return /^(P|DIV|PRE)$/.test(b.tagName); });
    if (!blocks.length) { return { on: false }; }
    var tag = wantOrdered ? 'ol' : 'ul';
    var html = '<' + tag + '>' + blocks.map(function (b) {
      var inner = b.innerHTML.replace(/^\s+|\s+$/g, '').replace(/<br>$/, '');
      return '<li>' + (inner || '<br>') + '</li>';
    }).join('') + '</' + tag + '>';
    var r = document.createRange();
    r.setStartBefore(blocks[0]);
    r.setEndAfter(blocks[blocks.length - 1]);
    var s = window.getSelection();
    s.removeAllRanges();
    s.addRange(r);
    exec('insertHTML', html);
    return { on: !!closest('li') };
  }

  function toggleQuote() {
    if (closest('blockquote')) { exec('outdent'); return { on: false }; }
    if (closest('li')) { leaveList(true); }
    exec('formatBlock', '<blockquote>');
    return { on: !!closest('blockquote') };
  }

  function align(cls) {
    var sel = window.getSelection();
    var block = sel && sel.rangeCount ? blockOf(sel.anchorNode) : null;
    var map = { 'align-left': 'justifyLeft', 'align-center': 'justifyCenter', 'align-right': 'justifyRight', 'align-justify': 'justifyFull' };
    exec(map[cls]);
    // execCommand writes a style attribute; the class is what the PDF
    // stylesheet understands, so carry it as well. The sanitiser folds
    // the style into the class either way.
    var blocks = [];
    var s = window.getSelection();
    if (s && s.rangeCount) {
      var r = s.getRangeAt(0);
      var startBlock = blockOf(r.startContainer), endBlock = blockOf(r.endContainer);
      if (startBlock) { blocks.push(startBlock); }
      if (endBlock && endBlock !== startBlock) { blocks.push(endBlock); }
    }
    blocks.forEach(function (b) {
      b.classList.remove('align-left', 'align-center', 'align-right', 'align-justify');
      if (cls !== 'align-left') { b.classList.add(cls); }
    });
    return { align: cls.replace('align-', '') };
  }

  function toggleCode() {
    var code = closest('code');
    var sel = window.getSelection();
    if (code) {
      // Code off removes the fixed width run the caret is in, whether or
      // not anything is selected, and leaves its text as ordinary text.
      selectNode(code);
      exec('insertText', code.textContent);
      return { on: false };
    }
    if (sel.isCollapsed) { return { on: false, nothing: true }; }
    var text = sel.toString();
    exec('insertHTML', '<code>' + escapeHtml(text) + '</code>');
    return { on: true };
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function inlineToggle(cmd) {
    exec(cmd);
    return { on: document.queryCommandState(cmd) };
  }

  // Backspace at the very start of a list item takes it out of the list.
  function unlistOnBackspace() {
    var li = closest('li');
    var sel = window.getSelection();
    if (!li || !sel || !sel.isCollapsed) { return false; }
    var r = sel.getRangeAt(0);
    var probe = document.createRange();
    probe.selectNodeContents(li);
    probe.setEnd(r.startContainer, r.startOffset);
    if (probe.toString().length !== 0) { return false; }
    exec('outdent');
    return true;
  }

  // Enter inside a figure caption starts a paragraph after the figure.
  function enterInFigure() {
    var fig = closest('figure');
    if (!fig) { return false; }
    var r = document.createRange();
    r.setStartAfter(fig); r.collapse(true);
    var s = window.getSelection();
    s.removeAllRanges(); s.addRange(r);
    exec('insertParagraph');
    var next = fig.nextElementSibling;
    if (next) {
      placeCaret(next, true);
      if (next.tagName !== 'P') { exec('formatBlock', '<p>'); }
    }
    return true;
  }

  function cellOf() { return closest('td,th'); }

  function applies(action) {
    if (action === 'indent' || action === 'outdent') { return !!(closest('li') || cellOf()); }
    if (action === 'delete_object') {
      if (figureAtCaret()) { return true; }
      var t = closest('table');
      return !!t && tableIsEmpty(t);
    }
    return true;
  }

  function tableIsEmpty(t) {
    return (t.innerText || '').replace(/\s+/g, '') === '';
  }

  function moveCell(forward) {
    var cell = cellOf();
    if (!cell) { return { moved: false }; }
    var table = cell.closest('table');
    var cells = Array.prototype.slice.call(table.querySelectorAll('th,td'));
    var i = cells.indexOf(cell);
    var target = cells[i + (forward ? 1 : -1)];
    if (!target && forward) {
      var cols = cells.filter(function (c) { return c.parentNode === cell.parentNode; }).length;
      var row = '<tr>' + new Array(cols + 1).join('<td><br></td>') + '</tr>';
      var html = table.outerHTML;
      var body = html.lastIndexOf('</tbody>');
      html = body >= 0 ? html.slice(0, body) + row + html.slice(body)
                       : html.replace(/<\/table>\s*$/i, row + '</table>');
      selectNode(table);
      exec('insertHTML', html);
      var all = tables();
      var made = all[all.length - 1];
      var again = Array.prototype.slice.call(made.querySelectorAll('th,td'));
      target = again[cells.length];
      if (target) { placeCaret(target, true); }
      return { moved: true, added: true };
    }
    if (target) { placeCaret(target, true); return { moved: true }; }
    return { moved: false };
  }

  function headingsList() {
    return Array.prototype.slice.call(ed.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(function (h, i) {
      return { index: i, level: +h.tagName[1], text: h.textContent.trim() };
    });
  }

  function goHeading(forward) {
    var all = Array.prototype.slice.call(ed.querySelectorAll('h1,h2,h3,h4,h5,h6'));
    var sel = window.getSelection();
    var here = sel && sel.rangeCount ? sel.anchorNode : null;
    var current = here ? blockOf(here) : null;
    var target = null;
    if (!here || !ed.contains(here)) { target = forward ? all[0] : all[all.length - 1]; }
    else {
      var r = sel.getRangeAt(0);
      for (var i = 0; i < all.length; i++) {
        var h = forward ? all[i] : all[all.length - 1 - i];
        if (h === current) { continue; }
        var cmp = r.comparePoint(h, 0);
        if (forward ? cmp === 1 : cmp === -1) { target = h; break; }
      }
    }
    if (!target) { return { found: false }; }
    placeCaret(target, true);
    target.scrollIntoView({ block: 'center' });
    return { found: true, level: +target.tagName[1], text: target.textContent.trim() };
  }

  // ------------------------------------------------- the screen settings --
  // Everything here writes a custom property on the html element or the
  // caret box outside the editor. Not one of them touches the text, so the
  // exported PDF, which is built from the body HTML alone, is always black
  // on white at the page size Document properties says.
  function applyZoom() {
    document.body.style.zoom = display.zoom / 100;
    layCaret();
    return { percent: display.zoom };
  }

  function setZoom(percent) {
    percent = Math.max(70, Math.min(300, Math.round(percent || 100)));
    display.zoom = percent;
    return applyZoom();
  }

  function zoom(delta) {
    // The keys step through the list; the Display page takes any number in
    // the range, so a person sitting at 210 steps to 250 and to 200.
    if (!delta) { return setZoom(100); }
    var i, next = display.zoom;
    if (delta > 0) {
      next = ZOOMS[ZOOMS.length - 1];
      for (i = 0; i < ZOOMS.length; i++) { if (ZOOMS[i] > display.zoom) { next = ZOOMS[i]; break; } }
    } else {
      next = ZOOMS[0];
      for (i = ZOOMS.length - 1; i >= 0; i--) { if (ZOOMS[i] < display.zoom) { next = ZOOMS[i]; break; } }
    }
    return setZoom(next);
  }

  // The caret box. The browser's own caret is one CSS pixel wide, which is
  // gone against a large font, and there is no property that widens it, so
  // a box of the asked for width is drawn over the collapsed selection and
  // the native caret is hidden. At the default of two pixels none of this
  // runs and the native caret is the one you see.
  var caretBox = null, caretTimer = 0;

  function caretElement() {
    if (!caretBox) {
      caretBox = document.createElement('div');
      caretBox.id = 'tgcaret';
      caretBox.setAttribute('aria-hidden', 'true');
      document.body.appendChild(caretBox);
    }
    return caretBox;
  }

  function fatCaret() { return (display.caret || 2) > 2; }

  function layCaret() {
    if (!fatCaret()) {
      if (caretBox) { caretBox.style.display = 'none'; }
      document.documentElement.removeAttribute('data-fatcaret');
      return;
    }
    document.documentElement.setAttribute('data-fatcaret', '1');
    var box = caretElement();
    var sel = window.getSelection();
    if (!sel || !sel.rangeCount || !sel.isCollapsed || !ed.contains(sel.anchorNode)
        || document.activeElement !== ed) {
      box.style.display = 'none';
      return;
    }
    var r = sel.getRangeAt(0);
    var rect = r.getClientRects()[0] || r.getBoundingClientRect();
    if (!rect || (!rect.height && !rect.top)) {
      // An empty paragraph gives a collapsed range no rectangle of its own.
      var b = blockOf(sel.anchorNode) || ed;
      var br = b.getBoundingClientRect();
      var pad = parseFloat(window.getComputedStyle(b).paddingLeft) || 0;
      rect = { left: br.left + pad, top: br.top, height: br.height || 20 };
    }
    box.style.width = display.caret + 'px';
    box.style.height = Math.max(12, Math.round(rect.height)) + 'px';
    box.style.left = Math.round(rect.left) + 'px';
    box.style.top = Math.round(rect.top) + 'px';
    box.style.display = 'block';
  }

  function scheduleCaret() {
    if (!fatCaret()) { return; }
    if (caretTimer) { return; }
    caretTimer = setTimeout(function () { caretTimer = 0; layCaret(); }, 16);
  }

  function setDisplay(d) {
    d = d || {};
    var root = document.documentElement;
    ['zoom', 'theme', 'caret', 'focus', 'bold', 'spacing'].forEach(function (k) {
      if (d[k] !== undefined && d[k] !== null) { display[k] = d[k]; }
    });
    root.setAttribute('data-theme', display.theme || 'normal');
    root.style.setProperty('--caret-width', (display.caret || 2) + 'px');
    root.style.setProperty('--focus-width', (display.focus || 3) + 'px');
    root.style.setProperty('--body-weight', display.bold ? 'bold' : 'normal');
    root.style.setProperty('--line-height', String(SPACING[display.spacing] || 1.5));
    applyZoom();
    layCaret();
    return { zoom: display.zoom, theme: display.theme, caret: display.caret,
             focus: display.focus, bold: !!display.bold, spacing: display.spacing };
  }

  var ACTIONS = {
    bold: function () { return inlineToggle('bold'); },
    italic: function () { return inlineToggle('italic'); },
    underline: function () { return inlineToggle('underline'); },
    strike: function () { return inlineToggle('strikeThrough'); },
    code: toggleCode,
    normal: function () { return setBlock('p'); },
    heading1: function () { return setBlock('h1'); },
    heading2: function () { return setBlock('h2'); },
    heading3: function () { return setBlock('h3'); },
    heading4: function () { return setBlock('h4'); },
    heading5: function () { return setBlock('h5'); },
    heading6: function () { return setBlock('h6'); },
    bullets: function () { return toggleList('insertUnorderedList', false); },
    numbers: function () { return toggleList('insertOrderedList', true); },
    quote: toggleQuote,
    align_left: function () { return align('align-left'); },
    align_center: function () { return align('align-center'); },
    align_right: function () { return align('align-right'); },
    align_justify: function () { return align('align-justify'); },
    undo: undoStep,
    redo: redoStep,
    cut: function () { exec('cut'); return {}; },
    copy: function () { exec('copy'); return {}; },
    select_all: function () { exec('selectAll'); return {}; },
    indent: function () { if (cellOf()) { return moveCell(true); } exec('indent'); return { on: true }; },
    outdent: function () { if (cellOf()) { return moveCell(false); } exec('outdent'); return { on: false }; },
    delete_object: function () {
      var fig = figureAtCaret();
      if (fig) { return { forward: true, object: 'figure', index: figures().indexOf(fig) }; }
      var t = closest('table');
      if (t) { return { forward: true, object: 'table', index: tables().indexOf(t) }; }
      return { forward: false };
    },
    next_heading: function () { return goHeading(true); },
    previous_heading: function () { return goHeading(false); },
    zoom_in: function () { return zoom(1); },
    zoom_out: function () { return zoom(-1); },
    zoom_reset: function () { return zoom(0); }
  };

  function run(action) {
    var fn = ACTIONS[action];
    if (!fn) { return { error: 'unknown action ' + action }; }
    var result = fn() || {};
    if (result.forward) { post({ type: 'key', action: action, object: result.object, index: result.index }); }
    else { result.action = action; result.block = currentBlockName(); post({ type: 'did', action: action, result: result }); }
    postState();
    return result;
  }

  // ---------------------------------------------------------- paste, drop --
  function readFileAsDataUrl(file, done) {
    var reader = new FileReader();
    reader.onload = function () { done(reader.result); };
    reader.onerror = function () { done(null); };
    reader.readAsDataURL(file);
  }

  function pictureFiles(list) {
    var out = [];
    if (!list) { return out; }
    for (var i = 0; i < list.length; i++) {
      var f = list[i];
      if (f && /^image\//.test(f.type)) { out.push(f); }
    }
    return out;
  }

  ed.addEventListener('paste', function (e) {
    e.preventDefault();
    var cd = e.clipboardData;
    if (!cd) { return; }
    var pics = pictureFiles(cd.files);
    if (pics.length) {
      readFileAsDataUrl(pics[0], function (url) { post({ type: 'paste', image: url, name: pics[0].name || '' }); });
      return;
    }
    var html = cd.getData('text/html') || '';
    var text = cd.getData('text/plain') || '';
    post({ type: 'paste', html: html, text: text });
  }, true);

  document.addEventListener('dragover', function (e) { e.preventDefault(); }, true);
  document.addEventListener('drop', function (e) {
    e.preventDefault();
    var dt = e.dataTransfer;
    if (!dt) { return; }
    var pics = pictureFiles(dt.files);
    if (pics.length) {
      readFileAsDataUrl(pics[0], function (url) { post({ type: 'paste', image: url, name: pics[0].name || '' }); });
      return;
    }
    var html = dt.getData('text/html') || '';
    var text = dt.getData('text/plain') || '';
    if (html || text) { post({ type: 'paste', html: html, text: text }); }
  }, true);

  // ------------------------------------------------ the API Python calls --
  function cleanBody() {
    var clone = ed.cloneNode(true);
    Array.prototype.slice.call(clone.querySelectorAll('*')).forEach(function (el) {
      el.classList.remove('epdf-here');
      if (el.getAttribute('class') === '') { el.removeAttribute('class'); }
      el.removeAttribute('contenteditable');
      el.removeAttribute('spellcheck');
    });
    return clone.innerHTML;
  }

  function figureHtml(spec) {
    var cls = 'width-' + (spec.width || 'half') + ' place-' + (spec.place || 'centre');
    var img = '<img src="' + escapeHtml(spec.src || '') + '" alt="' + escapeHtml(spec.decorative ? '' : (spec.alt || '')) + '"';
    if (spec.decorative) { img += ' role="presentation"'; }
    if (!spec.decorative && !(spec.alt || '').trim()) { img += ' data-needs-alt="1"'; }
    if (spec.altSource) { img += ' data-alt-source="' + escapeHtml(spec.altSource) + '"'; }
    img += '>';
    var cap = (spec.caption || '').trim() ? '<figcaption>' + escapeHtml(spec.caption.trim()) + '</figcaption>' : '';
    return '<figure class="' + cls + '">' + img + cap + '</figure>';
  }

  function findText(text, forward, matchCase) {
    if (!text) { return false; }
    var sel = window.getSelection();
    // window.find searches from the current selection; when the editor holds
    // no selection yet, start from the top so the first match is the first.
    if (!sel.rangeCount || !ed.contains(sel.anchorNode)) { placeCaret(ed, true); }
    var found = window.find(text, !!matchCase, !forward, true, false, false, false);
    if (found) {
      var s = window.getSelection();
      if (s.rangeCount && !ed.contains(s.anchorNode)) { found = false; }
    }
    return !!found;
  }

  function replaceAll(find, repl, matchCase) {
    if (!find) { return { count: 0 }; }
    var clone = ed.cloneNode(true);
    var walker = document.createTreeWalker(clone, NodeFilter.SHOW_TEXT, null);
    var count = 0, nodes = [];
    while (walker.nextNode()) { nodes.push(walker.currentNode); }
    var re = new RegExp(find.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), matchCase ? 'g' : 'gi');
    nodes.forEach(function (n) {
      var before = n.nodeValue;
      var hits = before.match(re);
      if (hits) {
        count += hits.length;
        n.nodeValue = before.replace(re, function (hit) { return matchCase ? repl : adaptCase(hit, repl); });
      }
    });
    if (!count) { return { count: 0 }; }
    var before = ed.innerHTML;
    ed.innerHTML = clone.innerHTML;
    replacedAll = { before: before, after: ed.innerHTML, restored: false };
    placeCaret(ed, true);
    ed.focus();
    scheduleWords();
    return { count: count, route: 'innerHTML' };
  }

  // With Match case off, a match spelt "Cats" or "CATS" gets its
  // replacement spelt the same way, as Word does it.
  function adaptCase(hit, repl) {
    if (!hit || !repl) { return repl; }
    if (hit === hit.toUpperCase() && hit !== hit.toLowerCase() && hit.length > 1) { return repl.toUpperCase(); }
    if (hit[0] === hit[0].toUpperCase() && hit[0] !== hit[0].toLowerCase()) { return repl[0].toUpperCase() + repl.slice(1); }
    return repl;
  }

  var replacedAll = null;
  function undoStep() {
    if (replacedAll && !replacedAll.restored && ed.innerHTML === replacedAll.after) {
      ed.innerHTML = replacedAll.before;
      replacedAll.restored = true;
      placeCaret(ed, true);
      scheduleWords();
      return { restored: 'replace all' };
    }
    exec('undo');
    return {};
  }
  function redoStep() {
    if (replacedAll && replacedAll.restored && ed.innerHTML === replacedAll.before) {
      ed.innerHTML = replacedAll.after;
      replacedAll.restored = false;
      placeCaret(ed, true);
      scheduleWords();
      return { redone: 'replace all' };
    }
    exec('redo');
    return {};
  }

  window.editor = {
    setBody: function (html) {
      ed.innerHTML = html && html.trim() ? html : '<p><br></p>';
      // Bare text at the top level would be tagged as nothing; give it a p.
      var loose = Array.prototype.slice.call(ed.childNodes).some(function (n) {
        return n.nodeType === 3 ? n.nodeValue.trim() !== '' : !/^(H[1-6]|P|UL|OL|BLOCKQUOTE|FIGURE|TABLE|HR|PRE|DIV)$/.test(n.tagName);
      });
      if (loose) {
        var p = null;
        Array.prototype.slice.call(ed.childNodes).forEach(function (n) {
          var block = n.nodeType === 1 && /^(H[1-6]|P|UL|OL|BLOCKQUOTE|FIGURE|TABLE|HR|PRE|DIV)$/.test(n.tagName);
          if (block) { p = null; return; }
          if (!p) { p = document.createElement('p'); ed.insertBefore(p, n); }
          p.appendChild(n);
        });
      }
      placeCaret(ed, true);
      applyZoom();
      scheduleWords();
      postState();
      return { ok: true, words: wordCount() };
    },
    getBody: cleanBody,
    wordCount: wordCount,
    state: stateObject,
    focus: function () { ed.focus(); postState(); return { focused: document.activeElement === ed }; },
    caretToStart: function () { placeCaret(ed, true); return {}; },
    caretToEnd: function () { placeCaret(ed, false); return {}; },
    apply: run,
    insertHTML: function (html) { exec('insertHTML', html); postState(); return { ok: true }; },
    insertText: function (text) { exec('insertText', text); postState(); return { ok: true }; },
    typeText: function (text) { exec('insertText', text); postState(); return { ok: true }; },
    linkAtCaret: function () {
      var a = closest('a');
      var sel = window.getSelection();
      return { link: a ? { text: a.textContent, href: a.getAttribute('href') || '' } : null,
               selected: (sel && !sel.isCollapsed) ? sel.toString() : '' };
    },
    insertLink: function (text, href) {
      // An existing link at the caret is replaced whole; a selection is
      // replaced by the link; a collapsed caret gets the link inserted.
      var a = closest('a');
      if (a) { selectNode(a); }
      exec('insertHTML', '<a href="' + escapeHtml(href) + '">' + escapeHtml(text) + '</a>');
      postState();
      return { ok: true };
    },
    unlink: function () {
      var a = closest('a');
      if (!a) { return { ok: false }; }
      selectNode(a); exec('insertText', a.textContent); return { ok: true };
    },
    insertFigure: function (spec) {
      var block = currentBlockName();
      var sel = window.getSelection();
      var atEnd = false;
      if (sel && sel.rangeCount) {
        var b = blockOf(sel.anchorNode);
        if (b) { var probe = document.createRange(); probe.selectNodeContents(b); probe.setStart(sel.getRangeAt(0).endContainer, sel.getRangeAt(0).endOffset); atEnd = probe.toString() === ''; }
      }
      if (closest('li')) { leaveList(true); }
      var html = figureHtml(spec);
      exec('insertHTML', html + '<p><br></p>');
      postState();
      return { ok: true, index: figures().length - 1, block: block, atEnd: atEnd };
    },
    figureAtCaret: function () { return figureInfo(figureAtCaret()); },
    updateFigure: function (index, spec) {
      var fig = figures()[index];
      if (!fig) { return { ok: false }; }
      var img = fig.querySelector('img');
      if (spec.src === undefined && img) { spec.src = img.getAttribute('src') || ''; }
      selectNode(fig);
      exec('insertHTML', figureHtml(spec));
      postState();
      return { ok: true };
    },
    removeObject: function (kind, index) {
      var node = (kind === 'figure' ? figures() : tables())[index];
      if (!node) { return { ok: false }; }
      if (kind === 'table') {
        // Measured: selecting the table node and deleting removes it and
        // keeps the paragraphs either side apart; the range route used for
        // figures merges them instead.
        selectNode(node);
        exec('delete');
        if (!ed.firstChild) { ed.innerHTML = '<p><br></p>'; }
        postState();
        return { ok: true, remains: node.parentNode === ed };
      }
      var before = node.previousSibling;
      while (before && before.nodeType === 3 && !before.nodeValue.trim()) { before = before.previousSibling; }
      var anchor = null;
      if (before && before.nodeType === 1 && /^(P|H[1-6]|BLOCKQUOTE|LI|UL|OL|DIV|PRE)$/.test(before.tagName)) {
        var walker = document.createTreeWalker(before, NodeFilter.SHOW_TEXT, null);
        var last = null;
        while (walker.nextNode()) { last = walker.currentNode; }
        if (last) { anchor = { node: last, offset: last.nodeValue.length }; }
        else { anchor = { node: before, offset: before.childNodes.length }; }
      }
      if (!anchor) {
        // A figure with no text block before it. insertHTML at that spot
        // puts the paragraph inside the figure (measured), so the empty
        // paragraph goes in by plain DOM insertion; it is harmless, it is
        // what the delete below anchors on, and undo restores the figure
        // after it.
        var made = document.createElement('p');
        made.innerHTML = '<br>';
        ed.insertBefore(made, node);
        anchor = { node: made, offset: 0 };
      }
      var r = document.createRange();
      r.setStart(anchor.node, anchor.offset);
      r.setEnd(node, node.childNodes.length);
      var sel = window.getSelection();
      sel.removeAllRanges(); sel.addRange(r);
      exec('delete');
      if (!ed.firstChild) { ed.innerHTML = '<p><br></p>'; }
      postState();
      return { ok: true, remains: node.parentNode === ed };
    },
    pictures: function () { return figures().map(function (f) { return figureInfo(f); }); },
    goToPicture: function (index) {
      var fig = figures()[index];
      if (!fig) { return { ok: false }; }
      var cap = fig.querySelector('figcaption');
      placeCaret(cap || fig, !cap);
      fig.scrollIntoView({ block: 'center' });
      ed.focus();
      postState();
      return { ok: true };
    },
    headings: headingsList,
    goToHeading: function (index) {
      var h = ed.querySelectorAll('h1,h2,h3,h4,h5,h6')[index];
      if (!h) { return { ok: false }; }
      placeCaret(h, true);
      h.scrollIntoView({ block: 'center' });
      ed.focus();
      postState();
      return { ok: true, level: +h.tagName[1], text: h.textContent.trim() };
    },
    insertTable: function (rows, cols, headerRow) {
      rows = Math.max(1, rows | 0); cols = Math.max(1, cols | 0);
      var html = '<table>';
      var r0 = 0;
      if (headerRow) {
        html += '<thead><tr>' + new Array(cols + 1).join('<th scope="col"><br></th>') + '</tr></thead>';
        r0 = 1;
      }
      html += '<tbody>';
      for (var r = r0; r < rows; r++) { html += '<tr>' + new Array(cols + 1).join('<td><br></td>') + '</tr>'; }
      if (rows <= r0) { html += '<tr>' + new Array(cols + 1).join('<td><br></td>') + '</tr>'; }
      html += '</tbody></table><p><br></p>';
      if (closest('li')) { leaveList(true); }
      exec('insertHTML', html);
      var all = tables();
      var made = all[all.length - 1];
      if (made) { var first = made.querySelector('th,td'); if (first) { placeCaret(first, true); } }
      postState();
      return { ok: true, index: all.length - 1 };
    },
    tableAtCaret: function () {
      var t = closest('table');
      return t ? { index: tables().indexOf(t), empty: tableIsEmpty(t) } : null;
    },
    find: function (text, forward, matchCase) {
      var found = findText(text, forward, matchCase);
      var sel = window.getSelection();
      var context = '';
      if (found && sel.rangeCount) {
        var b = blockOf(sel.anchorNode);
        context = b ? b.textContent.trim().slice(0, 120) : sel.toString();
      }
      postState();
      return { found: found, context: context };
    },
    replaceSelection: function (text, find, matchCase) {
      var sel = window.getSelection();
      if (!sel || sel.isCollapsed || !ed.contains(sel.anchorNode)) { return { replaced: false }; }
      var current = sel.toString();
      var same = matchCase ? current === find : current.toLowerCase() === find.toLowerCase();
      if (find && !same) { return { replaced: false }; }
      exec('insertText', matchCase ? text : adaptCase(current, text));
      postState();
      return { replaced: true };
    },
    replaceAll: replaceAll,
    setLang: function (lang) { document.documentElement.lang = lang || 'en'; return { ok: true }; },
    setPage: function (page) {
      if (page.width) { ed.style.width = page.width; }
      if (page.height) { ed.style.minHeight = page.height; }
      if (page.margin) { ed.style.padding = page.margin; }
      if (page.font) { document.body.style.fontFamily = page.font; }
      if (page.px) { document.body.style.fontSize = page.px + 'px'; }
      return { ok: true };
    },
    zoom: function (delta) { return zoom(delta); },
    setZoom: function (percent) { return setZoom(percent); },
    setDisplay: setDisplay,
    display: function () { return setDisplay({}); },
    caretBox: function () {
      var box = document.getElementById('tgcaret');
      return { present: !!box, width: box ? box.style.width : "",
               shown: !!(box && box.style.display === 'block') };
    },
    devicePixelRatio: function () { return { ratio: window.devicePixelRatio }; }
  };

  document.execCommand('defaultParagraphSeparator', false, 'p');
  if (!ed.firstChild) { ed.innerHTML = '<p><br></p>'; }
  setDisplay({});
  document.addEventListener('selectionchange', scheduleCaret);
  ed.addEventListener('input', scheduleCaret);
  window.addEventListener('scroll', scheduleCaret, true);
  window.addEventListener('resize', scheduleCaret);
  ed.addEventListener('blur', function () { layCaret(); });
  ed.addEventListener('focus', function () { postState(); scheduleCaret(); });
  window.addEventListener('focus', function () { if (document.activeElement !== ed) { ed.focus(); } });
  post({ type: 'ready' });
  postState();
})();
"""


def _css_length_inches(value):
    return "%.3fin" % float(value)


def _pixels(points):
    """A font size in whole pixels. Measured: Chromium's editing commands
    leave `style="font-size: 11pt"` spans behind on every moved or inserted
    run when the page's size is written in points, and none when it is a
    whole number of pixels, because its redundant style check compares the
    strings. 11pt is 14.667px, so 15px."""
    try:
        return max(8, int(round(float(points) * 96.0 / 72.0)))
    except (TypeError, ValueError):
        return 15


def default_display():
    """The screen settings a page gets when the caller names none."""
    return {"zoom": settings_mod.DEFAULT_ZOOM,
            "theme": settings_mod.DEFAULT_PAGE_THEME,
            "caret": settings_mod.DEFAULT_CARET_WIDTH,
            "focus": settings_mod.DEFAULT_FOCUS_RING,
            "bold": False,
            "spacing": settings_mod.DEFAULT_LINE_SPACING}


def clean_display(display):
    """The screen settings, every one of them inside its own range.

    The page is handed these as JSON, so a value that came from a hand
    edited settings file cannot become script: each one is forced to a
    number, a boolean or a name from the list.
    """
    out = default_display()
    given = dict(display or {})
    out["zoom"] = settings_mod._whole(given.get("zoom"), settings_mod.MIN_ZOOM,
                                      settings_mod.MAX_ZOOM, settings_mod.DEFAULT_ZOOM)
    out["caret"] = settings_mod._whole(given.get("caret"), settings_mod.MIN_CARET_WIDTH,
                                       settings_mod.MAX_CARET_WIDTH,
                                       settings_mod.DEFAULT_CARET_WIDTH)
    out["focus"] = settings_mod._whole(given.get("focus"), settings_mod.MIN_FOCUS_RING,
                                       settings_mod.MAX_FOCUS_RING,
                                       settings_mod.DEFAULT_FOCUS_RING)
    if given.get("theme") in settings_mod.PAGE_THEMES:
        out["theme"] = given["theme"]
    if given.get("spacing") in settings_mod.LINE_SPACINGS:
        out["spacing"] = given["spacing"]
    out["bold"] = bool(given.get("bold"))
    return out


def build_page(bindings, deny, lang="en-US", page=None, body_html="",
               textbox_role=True, nonce=None, display=None):
    """The whole document, ready for WebView.SetPage.

    `bindings` and `deny` come from keymap.page_bindings() and
    keymap.DENY_CHORDS. `page` holds size, margin_inches, font_family and
    font_points (constants fill in what is missing). `display` holds the
    screen settings, which are the screen only. `body_html` must already
    be sanitised: this function trusts it, the wrapper does not.
    """
    page = dict(page or {})
    size = page.get("page_size") or page.get("size") or C.DEFAULT_PAGE_SIZE
    width, height = PAGE_DIMENSIONS.get(size, PAGE_DIMENSIONS[C.DEFAULT_PAGE_SIZE])
    margin = _css_length_inches(page.get("margin_inches", C.DEFAULT_MARGIN_INCHES))
    font = page.get("font_family") or C.DEFAULT_FONT_FAMILY
    points = page.get("font_points") or C.DEFAULT_FONT_POINTS
    nonce = nonce or secrets.token_urlsafe(18)
    css = _CSS % {"font": font, "px": _pixels(points), "width": width,
                  "height": height, "margin": margin}
    js = (_JS.replace("__BINDINGS__", json.dumps(list(bindings)))
             .replace("__DENY__", json.dumps(list(deny)))
             .replace("__ZOOMS__", json.dumps(list(settings_mod.ZOOM_STEPS)))
             .replace("__SPACING__", json.dumps(settings_mod.LINE_SPACING_VALUES))
             .replace("__DISPLAY__", json.dumps(clean_display(display))))
    role = ('role="textbox" aria-multiline="true" ' if textbox_role else "")
    csp = ("default-src 'none'; script-src 'nonce-%s'; style-src 'unsafe-inline'; "
           "img-src data:; base-uri 'none'; form-action 'none'" % nonce)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="%s">\n' % _attr(lang)
        + "<head>\n"
        + '<meta charset="utf-8">\n'
        + '<meta http-equiv="Content-Security-Policy" content="%s">\n' % csp
        + "<title>%s</title>\n" % C.APP_NAME
        + "<style>%s</style>\n" % css
        + "</head>\n<body>\n"
        + '<main id="editor" contenteditable="true" spellcheck="true" %s'
          'aria-label="Document text">\n' % role
        + (body_html or "<p><br></p>")
        + "\n</main>\n"
        + '<script nonce="%s">%s</script>\n' % (nonce, js)
        + "</body>\n</html>\n"
    )


def _attr(text):
    return (str(text).replace("&", "&amp;").replace('"', "&quot;")
            .replace("<", "&lt;").replace(">", "&gt;"))


def page_css_for(page):
    """What editor.setPage needs when the document properties change."""
    size = page.get("page_size") or C.DEFAULT_PAGE_SIZE
    width, height = PAGE_DIMENSIONS.get(size, PAGE_DIMENSIONS[C.DEFAULT_PAGE_SIZE])
    return {"width": width, "height": height,
            "margin": _css_length_inches(page.get("margin_inches", C.DEFAULT_MARGIN_INCHES)),
            "font": page.get("font_family") or C.DEFAULT_FONT_FAMILY,
            "px": _pixels(page.get("font_points") or C.DEFAULT_FONT_POINTS)}
