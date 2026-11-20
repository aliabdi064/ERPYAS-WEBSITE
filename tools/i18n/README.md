# Website languages

The English pages (`index.html`, `delete-account.html`, `success.html`) are the source.
`build.py` writes `zh/ hi/ ar/ de/ fa/` from them and the translations in `<lang>.json`,
and updates `sitemap.xml` and the language links in the English pages.

    python3 tools/i18n/build.py          # write the pages
    python3 tools/i18n/build.py --check  # only report; exit 1 if anything is missing or broken

After changing English text: run the build. It lists every new or changed text as **missing**
for each language (those parts stay English on that language's page until translated). Add the
translation to `<lang>.json` under `"text"` (page text, with the `<0>…</0>` tokens kept) or
`"js"` (texts set by the page's scripts), and build again.

`keep.json` lists texts that stay English everywhere (plan names, sample names, product names).
The build stops when a translation loses a token or `${…}` placeholder, or when a translated
page's structure differs from the English page.

Never edit the files in `zh/ hi/ ar/ de/ fa/` by hand: the next build overwrites them.
