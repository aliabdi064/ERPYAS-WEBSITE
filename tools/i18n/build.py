"""Builds the translated copies of the website: /zh/ /hi/ /ar/ /de/ /fa/ /es/ /pt/ /fr/ (English stays at /).

    python3 tools/i18n/build.py            # build every language, report anything untranslated
    python3 tools/i18n/build.py --check    # build in memory only; fail if a page would change or a text is missing

The English pages are the source. Each text block is looked up in tools/i18n/<lang>.json
("text": English block -> translation, "js": English script string -> translation). Inline tags are
numbered tokens (<0>…</0>), so a translation can move them but never add, drop or change them.
A text that has no translation stays English and is listed, so nothing is ever silently lost.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from segments import render, segments, tokens  # noqa: E402

SITE = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ORIGIN = "https://www.erpyas.com"
PAGES = {"index.html": "", "delete-account.html": "delete-account", "success.html": "success"}
LANGS = {
    "zh": {"dir": "ltr", "font": "Noto+Sans+SC:wght@400;500;700;900", "family": "'Noto Sans SC'"},
    "hi": {"dir": "ltr", "font": "Noto+Sans+Devanagari:wght@400;500;600;700;800", "family": "'Noto Sans Devanagari'"},
    "ar": {"dir": "rtl", "font": "Noto+Sans+Arabic:wght@400;500;600;700;800", "family": "'Noto Sans Arabic'"},
    "de": {"dir": "ltr", "font": None, "family": None},
    "fa": {"dir": "rtl", "font": "Vazirmatn:wght@400;500;600;700;800", "family": "'Vazirmatn'"},
    "es": {"dir": "ltr", "font": None, "family": None},
    "pt": {"dir": "ltr", "font": None, "family": None},
    "fr": {"dir": "ltr", "font": None, "family": None},
}
ALL = ["en"] + list(LANGS)
KEEP = {" ".join(k.split()) for k in json.loads((Path(__file__).resolve().parent / "keep.json").read_text())["keep"]}
SCRIPT = re.compile(r"(?s)(<script\b[^>]*>)(.*?)(</script>)")
JS_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"|\'((?:[^\'\\\n]|\\.)*)\'|`((?:[^`\\]|\\.)*)`')
ENTITY = re.compile(r"&(?:[A-Za-z][A-Za-z0-9]*|#[0-9]+|#x[0-9A-Fa-f]+);")


def norm(text: str) -> str:
    return " ".join(text.split())


def page_url(lang: str, page: str) -> str:
    return f"{ORIGIN}/" + ("" if lang == "en" else f"{lang}/") + page


def alternates(page: str) -> str:
    links = [f'<link rel="alternate" hreflang="{l}" href="{page_url(l, page)}">' for l in ALL]
    links.append(f'<link rel="alternate" hreflang="x-default" href="{page_url("en", page)}">')
    return "".join(links)


def escape_text(t: str) -> str:
    """A bare & becomes &amp; (entities the translator wrote stay as they are)."""
    return re.sub(r"&(?![A-Za-z][A-Za-z0-9]*;|#[0-9]+;|#x[0-9A-Fa-f]+;)", "&amp;", t)


def check_pair(key: str, value: str, where: str, problems: list):
    if tokens(key) != tokens(value):
        problems.append(f"{where}: tags differ\n  en: {key}\n  tr: {value}")
    if re.findall(r"\$\{[^}]*\}", key) != re.findall(r"\$\{[^}]*\}", value):
        problems.append(f"{where}: ${{…}} placeholders differ\n  en: {key}\n  tr: {value}")


def js_quote(value: str, quote: str) -> str:
    value = value.replace("\\", "\\\\")
    if quote != "`":
        value = value.replace(quote, "\\" + quote)
    return quote + value + quote


def translate_scripts(src: str, table: dict, used: set, problems: list) -> str:
    def body(m):
        open_tag, code, close = m.groups()
        if "tailwind.config" in code or "i18n:" in code or "src=" in open_tag:
            return m.group(0)

        def lit(lm):
            raw = next(g for g in lm.groups() if g is not None)
            quote = lm.group(0)[0]
            if raw not in table:
                return lm.group(0)
            used.add(raw)
            check_pair(raw, table[raw], "script", problems)
            return js_quote(table[raw], quote)
        return open_tag + JS_LITERAL.sub(lit, code) + close
    return SCRIPT.sub(body, src)


def localize_links(src: str, lang: str) -> str:
    """Relative files load from the site root; links between pages stay in this language."""
    def attr(m):
        name, quote, value = m.group(1), m.group(2), m.group(3)
        if re.match(r"(?i)^(?:[a-z][a-z0-9+.-]*:|#|//|\$|\{)", value) or not value:
            return m.group(0)
        if not value.startswith("/"):
            value = "/" + value
        if name == "href":
            path, _, rest = value.partition("#")
            path, q, query = path.partition("?")
            clean = path.rstrip("/") or "/"
            if clean == "/" or clean.lstrip("/").removesuffix(".html") in PAGES.values():
                page = clean.lstrip("/").removesuffix(".html").removesuffix("index")
                value = f"/{lang}/{page}" + (q + query) + (("#" + rest) if rest else "")
        return f"{name}={quote}{value}{quote}"
    return re.sub(r'\b(src|href)=(["\'])(.*?)\2', attr, src)


def head_extra(lang: str) -> str:
    cfg = LANGS[lang]
    parts = []
    if cfg["font"]:
        parts.append('<link rel="preconnect" href="https://fonts.googleapis.com">'
                     '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
                     f'<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family={cfg["font"]}&display=swap">')
    css = []
    if cfg["family"]:
        fam = cfg["family"]
        css.append(f"body,.font-sans,.font-display{{font-family:Inter,{fam},system-ui,sans-serif!important}}"
                   f".font-mono{{font-family:'JetBrains Mono','Fira Code',{fam},monospace!important}}")
    if cfg["dir"] == "rtl":
        css.append(
            "[dir=rtl] .text-left{text-align:right}"
            "[dir=rtl] .text-right{text-align:left}"
            "[dir=rtl] [class*=space-x-]>:not([hidden])~:not([hidden]){--tw-space-x-reverse:1!important}"
            "[dir=rtl] ol,[dir=rtl] ul{padding-right:1.25rem;padding-left:0}"
            "[dir=rtl] ul.list-none,[dir=rtl] ol.list-none{padding-right:0}"
            "[dir=rtl] pre,[dir=rtl] code,[dir=rtl] kbd,[dir=rtl] #code-snippet,[dir=rtl] .ltr{direction:ltr;unicode-bidi:isolate}"
            "[dir=rtl] pre,[dir=rtl] #code-snippet{text-align:left}"
            "[dir=rtl] .brand-ltr,[dir=rtl] #navbar .font-black.flex{direction:ltr}"
            "[dir=rtl] input[type=email]{direction:ltr;text-align:right}"
            "[dir=rtl] #billing-toggle{direction:ltr;transform:scaleX(-1)}"
            "[dir=rtl] *{letter-spacing:0!important}"
        )
    if lang in ("zh", "hi"):
        css.append(".tracking-widest,.tracking-wider{letter-spacing:.04em!important}")
    if css:
        parts.append("<style>" + "".join(css) + "</style>")
    return "".join(parts)


def build_page(name: str, lang: str, table: dict, js_table: dict, report: dict, problems: list) -> str:
    src = (SITE / name).read_text(encoding="utf-8")
    segs = segments(src)
    texts = [s for s in segs if s.kind == "text"]
    # An attribute inside an inline tag of a text block (e.g. <span data-mo="…">) is translated as part of
    # that block's tag, never as a separate edit overlapping the block.
    inner = [a for a in segs if a.kind == "attr" and any(t.start <= a.start < t.end for t in texts)]

    def attr_value(a):
        if a.key not in table:
            report.setdefault(a.key, set()).add(name)
            return None
        report.setdefault("__used__", set()).add(a.key)
        return escape_text(table[a.key]).replace('"', "&quot;")

    out, last = [], 0
    for seg in segs:
        if seg in inner:
            continue
        if seg.key not in table:
            report.setdefault(seg.key, set()).add(name)
            continue
        value = table[seg.key]
        report.setdefault("__used__", set()).add(seg.key)
        if seg.kind == "text":
            check_pair(seg.key, value, name, problems)
            tags = dict(seg.tags)
            for a in inner:
                if not seg.start <= a.start < seg.end:
                    continue
                tr = attr_value(a)
                raw = src[a.start:a.end]
                for tok, (opening, closing) in tags.items():
                    hit = re.search(r'(=\s*["\'])' + re.escape(raw) + r'(["\'])', opening)
                    if tr is not None and hit:
                        tags[tok] = (opening[:hit.start()] + hit.group(1) + tr + hit.group(2) + opening[hit.end():], closing)
                        break
            new = escape_text(render(value, tags))
        elif seg.kind == "attr":
            new = escape_text(value).replace('"', "&quot;")
        else:
            new = escape_text(value)
        out.append(src[last:seg.start])
        out.append(new)
        last = seg.end
    out.append(src[last:])
    page = "".join(out)

    used_js: set = set()
    page = translate_scripts(page, js_table, used_js, problems)
    report.setdefault("__js_used__", set()).update(used_js)

    cfg = LANGS[lang]
    page = re.sub(r'<html lang="en"', f'<html lang="{lang}" dir="{cfg["dir"]}"', page, count=1)
    page = re.sub(r"(?s)<!-- i18n:redirect -->.*?<!-- /i18n:redirect -->\n?", "", page)
    page = localize_links(page, lang)
    me = page_url(lang, PAGES[name])
    page = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + me + m.group(2), page)
    page = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + me + m.group(2), page)
    page = re.sub(r'<meta property="og:locale" content="[^"]*">', "", page)
    page = page.replace("<!-- /i18n:head -->", "<!-- /i18n:head -->" + head_extra(lang), 1)
    page = re.sub(r"(?s)<!-- i18n:alternates -->.*?<!-- /i18n:alternates -->",
                  lambda m: "<!-- i18n:alternates -->" + alternates(PAGES[name]) + "<!-- /i18n:alternates -->", page)
    page = page.replace("_replyto:email,", f'_replyto:email,"Website Language":"{lang}",', 1)
    return page


class _Shape(__import__("html.parser").parser.HTMLParser):
    """The page's skeleton: every tag with the attributes that are never translated, in order, plus any
    text that looks like leaked markup (name="…" or a stray < >)."""
    FREE = {"alt", "title", "placeholder", "aria-label", "data-mo", "data-yr", "content", "href", "src", "dir"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.shape, self.leaks, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag == "html":
            attrs = [(a, v) for a, v in attrs if a not in ("lang", "dir")]
        self.shape.append((tag, tuple(sorted((a, v) for a, v in attrs if a not in self.FREE)),
                           tuple(sorted(a for a, _ in attrs if a in self.FREE and a != "dir"))))
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        self.shape.append(("/" + tag,))
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and re.search(r'[A-Za-z-]+="|[<>]', data) and not re.search(r"&lt;|<\s*\d", data):
            self.leaks.append(" ".join(data.split())[:120])


def shape(page: str):
    page = re.sub(r"(?s)<!-- i18n:(redirect|head|alternates) -->.*?<!-- /i18n:\1 -->", "", page)
    page = re.sub(r"(?s)<head>.*?</head>", "<head></head>", page)  # fonts and styles differ on purpose
    parser = _Shape()
    parser.feed(page)
    return parser.shape, parser.leaks


def check_shape(name: str, lang: str, english: str, page: str, problems: list):
    from collections import Counter
    from segments import INLINE
    (full_a, en_leaks), (full_b, leaks) = shape(english), shape(page)
    # Block tags must stay in the same order; inline tags (<strong>, <a>, …) may move within a sentence,
    # so for them only the set must match.
    a = [t for t in full_a if t[0].lstrip("/") not in INLINE]
    b = [t for t in full_b if t[0].lstrip("/") not in INLINE]
    inline_a = Counter(t for t in full_a if t[0].lstrip("/") in INLINE)
    inline_b = Counter(t for t in full_b if t[0].lstrip("/") in INLINE)
    if inline_a != inline_b:
        diff = list(((inline_a - inline_b) + (inline_b - inline_a)).elements())[:3]
        problems.append(f"{lang}/{name}: inline tags differ from English: {diff}")
    if a != b:
        i = next((n for n, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        problems.append(f"{lang}/{name}: page structure differs from English at tag {i}: {a[i:i+2]} vs {b[i:i+2]}")
    for leak in leaks:
        if leak not in en_leaks:
            problems.append(f"{lang}/{name}: text looks like leaked markup: {leak}")


def english_with_alternates(name: str) -> str:
    src = (SITE / name).read_text(encoding="utf-8")
    return re.sub(r"(?s)<!-- i18n:alternates -->.*?<!-- /i18n:alternates -->",
                  lambda m: "<!-- i18n:alternates -->" + alternates(PAGES[name]) + "<!-- /i18n:alternates -->", src)


def sitemap() -> str:
    rows = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for page in ("", "delete-account"):
        for lang in ALL:
            rows.append(f"  <url>\n    <loc>{page_url(lang, page)}</loc>")
            for alt in ALL:
                rows.append(f'    <xhtml:link rel="alternate" hreflang="{alt}" href="{page_url(alt, page)}"/>')
            rows.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{page_url("en", page)}"/>\n  </url>')
    rows.append("</urlset>\n")
    return "\n".join(rows)


def main(argv):
    check = "--check" in argv
    problems, changed, missing_total = [], [], 0
    outputs = {}
    for name in PAGES:
        outputs[SITE / name] = english_with_alternates(name)
    outputs[SITE / "sitemap.xml"] = sitemap()
    for lang in LANGS:
        data = json.loads((HERE / f"{lang}.json").read_text(encoding="utf-8"))
        table = {norm(k): norm(v) for k, v in data["text"].items()}
        js_table = data.get("js", {})
        report: dict = {}
        for name in PAGES:
            outputs[SITE / lang / name] = build_page(name, lang, table, js_table, report, problems)
            check_shape(name, lang, outputs[SITE / name], outputs[SITE / lang / name], problems)
        used = report.pop("__used__", set())
        used_js = report.pop("__js_used__", set())
        missing = {k: v for k, v in report.items() if k not in KEEP}
        stale = [k for k in table if k not in used]
        stale_js = [k for k in js_table if k not in used_js]
        missing_total += len(missing)
        print(f"{lang}: {len(used)} texts + {len(used_js)} script texts translated, {len(missing)} missing, "
              f"{len(stale) + len(stale_js)} no longer on the site")
        for k, pages in list(missing.items())[:40]:
            print(f"   missing [{', '.join(sorted(pages))}]: {k[:110]}")
        for k in (stale + stale_js)[:10]:
            print(f"   unused: {k[:110]}")
    for path, text in outputs.items():
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old != text:
            changed.append(str(path.relative_to(SITE)))
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    for p in problems:
        print("PROBLEM:", p)
    if check:
        if changed:
            print("out of date:", ", ".join(changed))
        return 1 if (changed or problems or missing_total) else 0
    print("written:", ", ".join(changed) or "nothing changed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
