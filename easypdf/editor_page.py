"""The editor page: the HTML, CSS and JavaScript inside the WebView2.

One contenteditable region that only ever holds semantic markup, a key map
generated from easypdf/ui/keymap.py, and a message bridge to Python.

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

#: Widths of the page, in CSS units, for the paper on screen.
PAGE_DIMENSIONS = {
    "letter": ("8.5in", "11in"),
    "A4": ("210mm", "297mm"),
    "legal": ("8.5in", "14in"),
}

_CSS = """
html, body { margin: 0; padding: 0; background: #e3e6eb; color-scheme: light; }
body { font-family: %(font)s; font-size: %(px)spx; line-height: 1.5; }
#editor {
  box-sizing: border-box;
  background: #ffffff; color: #111111;
  width: %(width)s; max-width: calc(100vw - 32px); min-height: %(height)s;
  margin: 16px auto 32px auto; padding: %(margin)s;
  box-shadow: 0 1px 2px rgba(0,0,0,0.20), 0 6px 20px rgba(0,0,0,0.12);
  border: 1px solid #c8ccd4; border-radius: 2px;
  outline: none; caret-color: #000000;
  overflow-wrap: break-word;
}
#editor:focus { box-shadow: 0 0 0 3px #2b6fd6, 0 6px 20px rgba(0,0,0,0.12); border-color: #2b6fd6; }
#editor h1 { font-size: 2.0em; margin: 0.8em 0 0.35em; line-height: 1.2; }
#editor h2 { font-size: 1.6em; margin: 0.8em 0 0.35em; line-height: 1.25; }
#editor h3 { font-size: 1.3em; margin: 0.8em 0 0.3em; line-height: 1.3; }
#editor h4 { font-size: 1.15em; margin: 0.7em 0 0.3em; }
#editor h5 { font-size: 1.05em; margin: 0.6em 0 0.25em; }
#editor h6 { font-size: 1.0em; margin: 0.6em 0 0.25em; font-style: italic; }
#editor p { margin: 0 0 0.7em; }
#editor ul, #editor ol { margin: 0 0 0.7em; padding-left: 2.2em; }
#editor li { margin: 0 0 0.2em; }
#editor a { color: #0b4fb8; text-decoration: underline; }
#editor blockquote { margin: 0.6em 0 0.8em 1.6em; padding: 0.1em 0 0.1em 1em;
  border-left: 4px solid #b9c0cc; color: #333333; }
#editor blockquote p:last-child { margin-bottom: 0; }
#editor code { font-family: Consolas, "Courier New", monospace; font-size: 0.95em;
  background: #f1f3f6; padding: 0 0.2em; border-radius: 2px; }
#editor p.code-block { font-family: Consolas, "Courier New", monospace; white-space: pre-wrap;
  background: #f1f3f6; padding: 0.5em 0.7em; }
#editor figure { display: block; margin: 0.8em 0; padding: 0; max-width: 100%%; }
#editor figure img { display: block; width: 100%%; height: auto; }
#editor figcaption { font-size: 0.9em; color: #444444; margin-top: 0.35em; }
#editor figure.width-quarter { width: 25%%; }
#editor figure.width-half { width: 50%%; }
#editor figure.width-three-quarters { width: 75%%; }
#editor figure.width-full { width: 100%%; }
#editor figure.place-left { margin-right: auto; }
#editor figure.place-centre { margin-left: auto; margin-right: auto; }
#editor figure.place-right { margin-left: auto; }
#editor figure.epdf-here { outline: 2px dashed #2b6fd6; outline-offset: 3px; }
#editor table { border-collapse: collapse; margin: 0.6em 0 0.9em; width: 100%%; }
#editor th, #editor td { border: 1px solid #8f96a3; padding: 0.3em 0.5em; text-align: left;
  vertical-align: top; min-width: 2em; }
#editor th { background: #eef0f4; font-weight: bold; }
#editor .align-left { text-align: left; }
#editor .align-center { text-align: center; }
#editor .align-right { text-align: right; }
#editor .align-justify { text-align: justify; }
#editor hr { border: 0; border-top: 1px solid #8f96a3; margin: 1em 0; }
::selection { background: #b9d3ff; }
@media (forced-colors: active) {
  html, body { background: Canvas; }
  #editor { background: Canvas; color: CanvasText; border: 1px solid CanvasText; box-shadow: none; }
  #editor:focus { outline: 3px solid Highlight; outline-offset: 2px; box-shadow: none; }
  #editor a { color: LinkText; }
  #editor blockquote { border-left-color: CanvasText; color: CanvasText; }
  #editor code, #editor p.code-block, #editor th { background: Canvas; color: CanvasText; }
  #editor th, #editor td, #editor hr { border-color: CanvasText; }
  #editor figcaption { color: CanvasText; }
  #editor figure.epdf-here { outline-color: Highlight; }
}
"""

_JS = r"""
(function () {
  'use strict';
  var ed = document.getElementById('editor');
  var BIND = __BINDINGS__;
  var DENY = __DENY__;
  var BLOCKS = /^(H[1-6]|P|LI|BLOCKQUOTE|FIGURE|FIGCAPTION|TD|TH|PRE|DIV)$/;
  var ZOOMS = [0.7, 0.85, 1, 1.15, 1.3, 1.5, 1.75, 2, 2.5, 3];
  var zoomIndex = 2;

  function post(obj) {
    var text = JSON.stringify(obj);
    try { window.easypdf.postMessage(text); return; } catch (e) {}
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
    if (c === 'f10' || c === 'shift+f10' && false) {
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
      altSource: img ? (img.getAttribute('data-alt-source') || '') : '',
      needsAlt: !!img && (img.hasAttribute('data-needs-alt') || (!img.hasAttribute('alt'))),
      src: img ? (img.getAttribute('src') || '') : '' };
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

  function leaveLists() {
    var guard = 0;
    while (closest('li') && guard++ < 8) { exec('outdent'); }
    // Outdent leaves the item's text bare at the top level (measured:
    // "<p>One</p>Two<br><p>Three</p>"); give it its paragraph back.
    wrapBareText();
  }

  function setBlock(tag) {
    var was = currentBlockName();
    if (closest('li')) { leaveLists(); }
    if (closest('blockquote') && tag !== 'blockquote') { exec('outdent'); }
    exec('formatBlock', '<' + tag + '>');
    return { was: was, now: currentBlockName() };
  }

  function toggleList(cmd, wantOrdered) {
    var li = closest('li');
    if (li) {
      var isOrdered = li.closest('ol,ul').tagName === 'OL';
      if (isOrdered === wantOrdered) { leaveLists(); return { on: false }; }
    }
    var block = currentBlockName();
    if (/^h[1-6]$/.test(block)) { exec('formatBlock', '<p>'); }
    if (closest('blockquote')) { exec('outdent'); }
    exec(cmd);
    liftNestedLists();
    return { on: !!closest('li') };
  }

  // Measured: after any formatBlock round trip, insertUnorderedList puts
  // the new list INSIDE the paragraph it came from ("<p><ul><li>"), which
  // the PDF would tag as a paragraph holding a list. Lift such a list out
  // of a paragraph or heading wrapper and drop the wrapper if it is empty.
  function liftNestedLists() {
    Array.prototype.slice.call(ed.querySelectorAll('p > ul, p > ol, h1 > ul, h2 > ul, h3 > ul, h4 > ul, h5 > ul, h6 > ul, h1 > ol, h2 > ol, h3 > ol, h4 > ol, h5 > ol, h6 > ol')).forEach(function (list) {
      var wrap = list.parentNode;
      wrap.parentNode.insertBefore(list, wrap);
      if (!(wrap.textContent || '').trim() && !wrap.querySelector('img')) { wrap.parentNode.removeChild(wrap); }
    });
  }

  function toggleQuote() {
    if (closest('blockquote')) { exec('outdent'); return { on: false }; }
    if (closest('li')) { leaveLists(); }
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

  function zoom(delta) {
    if (delta === 0) { zoomIndex = 2; } else { zoomIndex = Math.max(0, Math.min(ZOOMS.length - 1, zoomIndex + delta)); }
    document.body.style.zoom = ZOOMS[zoomIndex];
    return { percent: Math.round(ZOOMS[zoomIndex] * 100) };
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
      zoom(0);
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
      if (closest('li')) { leaveLists(); }
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
      if (closest('li')) { leaveLists(); }
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
    devicePixelRatio: function () { return { ratio: window.devicePixelRatio }; }
  };

  document.execCommand('defaultParagraphSeparator', false, 'p');
  if (!ed.firstChild) { ed.innerHTML = '<p><br></p>'; }
  ed.addEventListener('focus', function () { postState(); });
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


def build_page(bindings, deny, lang="en-US", page=None, body_html="",
               textbox_role=True, nonce=None):
    """The whole document, ready for WebView.SetPage.

    `bindings` and `deny` come from keymap.page_bindings() and
    keymap.DENY_CHORDS. `page` holds size, margin_inches, font_family and
    font_points (constants fill in what is missing). `body_html` must already
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
             .replace("__DENY__", json.dumps(list(deny))))
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
