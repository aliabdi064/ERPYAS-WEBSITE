"""Finds the translatable text of an HTML page, with exact source positions (standard library only).

A *segment* is a run of text plus inline markup inside one block (a paragraph, a list item, a
button, a table cell …). Inline tags are replaced by numbered tokens so a translation can move
them but never change them:  'Take a photo or upload a <0>PDF</0>.'  where <0> is <strong>.
Scripts, styles and SVG drawings are never touched; attributes people read (alt, title,
placeholder, aria-label, meta descriptions) are segments of their own.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

INLINE = {"a", "abbr", "b", "br", "code", "em", "i", "img", "kbd", "mark", "q", "s", "small", "span", "strong",
          "sub", "sup", "u", "time", "wbr", "bdi", "bdo"}
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP = {"script", "style", "svg", "template", "noscript", "code", "pre", "textarea"}
ATTRS = {"alt", "title", "placeholder", "aria-label", "data-mo", "data-yr"}
META_NAMES = {"description", "og:title", "og:description", "twitter:title", "twitter:description",
              "apple-mobile-web-app-title"}
WORD = re.compile(r"[A-Za-z]{2,}")


@dataclass
class Node:
    tag: str
    start: int            # offset of "<"
    inner_start: int      # offset after ">"
    inner_end: int = -1   # offset of "</"
    end: int = -1         # offset after the end tag
    attrs: List[Tuple[str, Optional[str]]] = field(default_factory=list)
    children: list = field(default_factory=list)   # Node or (text_start, text_end)
    parent: Optional["Node"] = None


class _Tree(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self.src = source
        self.lines = [0]
        for m in re.finditer("\n", source):
            self.lines.append(m.end())
        self.root = Node("#root", 0, 0, len(source), len(source))
        self.stack = [self.root]
        self.attr_hits: List[Tuple[int, int, str]] = []  # (start, end, value) of readable attribute values
        self.title_hits: List[Tuple[int, int]] = []

    def _pos(self) -> int:
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def _attr_spans(self, start: int, tag_text: str, attrs):
        meta = dict(attrs)
        for name, value in attrs:
            if value is None:
                continue
            readable = name in ATTRS or (name == "content" and (meta.get("name") in META_NAMES or meta.get("property") in META_NAMES))
            if not readable or not WORD.search(html.unescape(value)):
                continue
            m = re.search(r'\b%s\s*=\s*(["\'])(.*?)\1' % re.escape(name), tag_text, re.S)
            if m:
                self.attr_hits.append((start + m.start(2), start + m.end(2), m.group(2)))

    def handle_starttag(self, tag, attrs):
        start = self._pos()
        text = self.get_starttag_text()
        node = Node(tag, start, start + len(text), attrs=attrs, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if not any(n.tag in SKIP for n in self.stack):
            self._attr_spans(start, text, attrs)
        if tag in VOID:
            node.inner_end = node.end = node.inner_start
        else:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        start = self._pos()
        text = self.get_starttag_text()
        node = Node(tag, start, start + len(text), start + len(text), start + len(text), attrs, parent=self.stack[-1])
        self.stack[-1].children.append(node)
        if not any(n.tag in SKIP for n in self.stack):
            self._attr_spans(start, text, attrs)

    def handle_endtag(self, tag):
        pos = self._pos()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                for n in self.stack[i:]:
                    n.inner_end = pos if n.tag == tag else pos
                    n.end = self.src.index(">", pos) + 1 if n.tag == tag else pos
                del self.stack[i:]
                return

    def handle_data(self, data):
        start = self._pos()
        self.stack[-1].children.append((start, start + len(data)))

    def handle_entityref(self, name):
        start = self._pos()
        self.stack[-1].children.append((start, start + len(name) + 2))

    def handle_charref(self, name):
        start = self._pos()
        self.stack[-1].children.append((start, start + len(name) + 3))


@dataclass
class Segment:
    start: int
    end: int
    key: str                 # the English with tokens, whitespace collapsed
    tags: Dict[str, Tuple[str, str]]  # token -> (opening tag source, closing tag source)
    kind: str = "text"       # text | attr | title


def _has_text(src: str, item) -> bool:
    if isinstance(item, tuple):
        return bool(WORD.search(html.unescape(src[item[0]:item[1]])))
    if item.tag in SKIP:
        return False
    return any(_has_text(src, c) for c in item.children)


def _pure_inline(item) -> bool:
    if isinstance(item, tuple):
        return True
    return item.tag in INLINE and all(_pure_inline(c) for c in item.children)


def _tokenize(src: str, items) -> Tuple[str, Dict[str, Tuple[str, str]]]:
    tags: Dict[str, Tuple[str, str]] = {}
    out: List[str] = []

    def walk(item):
        if isinstance(item, tuple):
            out.append(src[item[0]:item[1]])
            return
        token = str(len(tags))
        opening = src[item.start:item.inner_start]
        closing = src[item.inner_end:item.end] if item.end > item.inner_end else ""
        tags[token] = (opening, closing)
        if not item.children and (item.tag in VOID or not closing) or (item.tag == "i" and not item.children):
            out.append(f"<{token}/>")
            return
        out.append(f"<{token}>")
        for c in item.children:
            walk(c)
        out.append(f"</{token}>")

    for it in items:
        walk(it)
    return " ".join("".join(out).split()), tags


def _span(items) -> Tuple[int, int]:
    first, last = items[0], items[-1]
    return (first[0] if isinstance(first, tuple) else first.start), (last[1] if isinstance(last, tuple) else last.end)


def segments(source: str) -> List[Segment]:
    tree = _Tree(source)
    tree.feed(source)
    tree.close()
    found: List[Segment] = []

    def emit(items):
        # trim whitespace-only text at both ends
        while items and isinstance(items[0], tuple) and not source[items[0][0]:items[0][1]].strip():
            items = items[1:]
        while items and isinstance(items[-1], tuple) and not source[items[-1][0]:items[-1][1]].strip():
            items = items[:-1]
        if not items or not any(_has_text(source, i) for i in items):
            return
        start, end = _span(items)
        # leading/trailing whitespace inside the first/last text stays in place
        if isinstance(items[0], tuple):
            start += len(source[start:items[0][1]]) - len(source[start:items[0][1]].lstrip())
        if isinstance(items[-1], tuple):
            end -= len(source[items[-1][0]:end]) - len(source[items[-1][0]:end].rstrip())
        key, tags = _tokenize(source, [(start, items[0][1]) if isinstance(items[0], tuple) and len(items) > 1 else
                                       ((start, end) if isinstance(items[0], tuple) and len(items) == 1 else items[0])]
                              + items[1:-1] + ([(items[-1][0], end)] if isinstance(items[-1], tuple) and len(items) > 1
                                               else ([items[-1]] if len(items) > 1 else [])))
        found.append(Segment(start, end, key, tags))

    def visit(node: Node):
        if node.tag in SKIP:
            return
        if node.tag == "title":
            if node.children:
                s, e = _span(node.children)
                found.append(Segment(s, e, " ".join(source[s:e].split()), {}, "title"))
            return
        if node.tag not in INLINE and node.tag != "#root" and all(_pure_inline(c) for c in node.children):
            emit(list(node.children))
            return
        run: list = []
        for c in node.children:
            if isinstance(c, tuple) or _pure_inline(c):
                run.append(c)
            else:
                emit(run)
                run = []
                visit(c)
        emit(run)

    visit(tree.root)
    for s, e, value in tree.attr_hits:
        found.append(Segment(s, e, " ".join(value.split()), {}, "attr"))
    found.sort(key=lambda x: x.start)
    return found


def render(translation: str, tags: Dict[str, Tuple[str, str]]) -> str:
    """Tokens back to the page's own tags."""
    def sub(m):
        slash, token, self_close = m.group(1), m.group(2), m.group(3)
        opening, closing = tags[token]
        if self_close:
            return opening + closing
        return closing if slash else opening
    return re.sub(r"<(/?)(\d+)(/?)>", sub, translation)


def tokens(text: str) -> List[str]:
    return sorted(re.findall(r"</?\d+/?>", text))
