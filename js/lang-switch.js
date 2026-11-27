/* ERPYAS website language menu: a flag button that opens the ERPYAS languages (the app's languages).
   Each language is a full static copy of the site in its own folder (/zh/, /de/, /tr/, …; English at /).
   The choice is remembered in this browser only, so the next visit opens in the same language. */
(function () {
  var LANGS = [
    ["en", "gb", "English"], ["zh", "cn", "简体中文"], ["zh-tw", "tw", "繁體中文"], ["hi", "in", "हिन्दी"],
    ["ar", "ae", "العربية"], ["de", "de", "Deutsch"], ["fa", "fa", "فارسی"],
    ["es", "es", "Español"], ["pt", "pt", "Português (Portugal)"], ["pt-br", "br", "Português (Brasil)"], ["fr", "fr", "Français"],
    ["tr", "tr", "Türkçe"], ["nb", "no", "Norsk"], ["sv", "se", "Svenska"], ["sr", "rs", "Српски"], ["sr-latn", "rs", "Srpski"], ["hr", "hr", "Hrvatski"]
  ];
  var LABEL = { en: "Language", zh: "语言", "zh-tw": "語言", hi: "भाषा", ar: "اللغة", de: "Sprache", fa: "زبان",
                es: "Idioma", pt: "Idioma", "pt-br": "Idioma", fr: "Langue", tr: "Dil", nb: "Språk", sv: "Språk", sr: "Језик", "sr-latn": "Jezik", hr: "Jezik" };
  var KEY = "erpyas_lang";
  var cur = (document.documentElement.lang || "en").toLowerCase(); // a folder name: de, pt-br, sr-latn, zh-tw
  if (!LANGS.some(function (l) { return l[0] === cur; })) cur = "en";

  function page() {
    var dirs = new RegExp("^/(" + LANGS.map(function (l) { return l[0]; }).join("|") + ")(/|$)");
    return location.pathname.replace(dirs, "/").replace(/^\//, "")
      .replace(/(^|\/)index\.html$/, "$1").replace(/\.html$/, "");
  }
  function href(code) { return (code === "en" ? "/" : "/" + code + "/") + page() + location.search + location.hash; }
  function save(code) { try { localStorage.setItem(KEY, code); } catch (e) { /* private mode: still switches */ } }
  function flag(code, cls) {
    var img = document.createElement("img");
    img.src = "/img/flags/" + code + ".svg"; img.alt = ""; img.width = 24; img.height = 18;
    img.className = cls; img.decoding = "async";
    return img;
  }

  function build(host) {
    var me = LANGS.filter(function (l) { return l[0] === cur; })[0];
    var btn = document.createElement("button");
    btn.type = "button"; btn.className = "lang-btn";
    btn.setAttribute("aria-haspopup", "true"); btn.setAttribute("aria-expanded", "false");
    btn.setAttribute("aria-label", LABEL[cur] + ": " + me[2]); btn.title = LABEL[cur];
    btn.appendChild(flag(me[1], "lang-flag"));
    btn.insertAdjacentHTML("beforeend", '<svg class="lang-chev" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>');

    var menu = document.createElement("div");
    menu.className = "lang-menu"; menu.hidden = true; menu.setAttribute("role", "menu");
    LANGS.forEach(function (l) {
      var a = document.createElement("a");
      a.className = "lang-item"; a.dir = "ltr"; a.href = href(l[0]); a.lang = l[0]; a.setAttribute("role", "menuitem");
      if (l[0] === cur) a.setAttribute("aria-current", "true");
      a.appendChild(flag(l[1], "lang-flag lang-flag-lg"));
      var name = document.createElement("span"); name.textContent = l[2]; name.dir = "auto"; a.appendChild(name);
      a.addEventListener("click", function (e) {
        save(l[0]);
        if (l[0] === cur) { e.preventDefault(); close(); return; }
        a.href = href(l[0]); // the hash may have changed since the menu was built
      });
      menu.appendChild(a);
    });

    function open() { menu.hidden = false; btn.setAttribute("aria-expanded", "true"); host.classList.add("is-open"); }
    function close() { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); host.classList.remove("is-open"); }
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      if (menu.hidden) { open(); var c = menu.querySelector("[aria-current]"); if (c) c.focus({ preventScroll: true }); } else close();
    });
    document.addEventListener("click", function (e) { if (!host.contains(e.target)) close(); });
    host.addEventListener("keydown", function (e) {
      var items = Array.prototype.slice.call(menu.querySelectorAll(".lang-item"));
      var i = items.indexOf(document.activeElement);
      if (e.key === "Escape") { close(); btn.focus(); }
      else if (!menu.hidden && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
        e.preventDefault();
        var n = e.key === "ArrowDown" ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
        items[n].focus();
      }
    });
    host.textContent = ""; host.appendChild(btn); host.appendChild(menu);
  }

  function init() { Array.prototype.forEach.call(document.querySelectorAll("[data-lang-switch]"), build); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
