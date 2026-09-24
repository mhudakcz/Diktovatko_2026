"""Vygeneruje historii změn na webu z docs/changes.json.

- docs/zmeny.html, docs/en/zmeny.html, docs/de/zmeny.html: všechny verze (vzhled převzatý z návodu),
- sekce „Co je nového“ se třemi posledními verzemi na úvodních stránkách (mezi značkami novinky:start/end).

Při nové verzi stačí přidat záznam nahoru do docs/changes.json (cs, en, de) a spustit:
    .venv\\Scripts\\python tools\\build_changes.py
"""

import html
import json
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
LANGS = {"cs": "", "en": "en/", "de": "de/"}
MONTHS = {
    "cs": ["ledna", "února", "března", "dubna", "května", "června", "července", "srpna", "září", "října", "listopadu", "prosince"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
}
TXT = {
    "cs": dict(title="Historie změn Diktovátka", desc="Co a kdy v Diktovátku přibylo, verze po verzi.", h1="Historie změn",
               lede="Co a kdy v Diktovátku přibylo, od nejnovější verze. Aplikace se aktualizuje sama a před aktualizací vám změny ukáže.",
               ver="Verze", latest="nejnovější", toc="Verze", home="Zpět na úvod", guide="Návod",
               h2="Co je nového", intro="Diktovátko se vyvíjí průběžně. Tohle přibylo naposledy.", more="Celá historie změn", rail="Novinky"),
    "en": dict(title="Diktovátko changelog", desc="What was added to Diktovátko and when, version by version.", h1="Changelog",
               lede="What was added to Diktovátko and when, newest first. The app updates itself and shows you the changes before it does.",
               ver="Version", latest="latest", toc="Versions", home="Back to home", guide="Guide",
               h2="What's new", intro="Diktovátko keeps evolving. Here is what arrived most recently.", more="Full changelog", rail="What's new"),
    "de": dict(title="Diktovátko – Änderungsverlauf", desc="Was in Diktovátko wann dazukam, Version für Version.", h1="Änderungsverlauf",
               lede="Was in Diktovátko wann dazukam, die neueste Version zuerst. Die App aktualisiert sich selbst und zeigt Ihnen die Änderungen vorher an.",
               ver="Version", latest="neueste", toc="Versionen", home="Zurück zur Startseite", guide="Anleitung",
               h2="Neuigkeiten", intro="Diktovátko wird laufend weiterentwickelt. Das kam zuletzt dazu.", more="Vollständiger Änderungsverlauf", rail="Neuigkeiten"),
}
PAGE_CSS = """
.layout.clog { grid-template-columns: 200px 1fr; }
.clog .toc a::before { content: none; }
.rel { padding: 26px 0; border-top: 1px solid var(--line); scroll-margin-top: 90px; }
.rel:first-of-type { border-top: 0; }
.rel h2 { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; margin: 0 0 10px; font: 700 22px/1.2 var(--display); letter-spacing: -0.02em; }
.rel time { font: 500 14px var(--body); color: var(--muted); letter-spacing: 0; }
.rel .new { font: 700 12px/1 var(--body); padding: 5px 9px; border-radius: 999px; background: var(--sun); color: var(--night); letter-spacing: 0; }
.rel ul { margin: 0; padding-left: 20px; display: grid; gap: 6px; color: var(--ink-2); }
.clog-links { display: flex; flex-wrap: wrap; gap: 10px 20px; margin: 18px 0 8px; font-weight: 600; }
@media (max-width: 860px) { .layout.clog { grid-template-columns: 1fr; } .clog .toc { display: none; } }
"""
HOME_CSS = """<style>
.news-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 48px; }
.news { padding: 26px 26px 24px; border-radius: 22px; background: var(--card); border: 1px solid var(--line); }
.news h3 { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; font: 700 20px/1.2 var(--display); letter-spacing: -0.02em; }
.news time { font: 500 13px var(--body); color: var(--muted); letter-spacing: 0; }
.news .new { font: 700 11px/1 var(--body); padding: 4px 8px; border-radius: 999px; background: var(--sun); color: #16133A; letter-spacing: 0; }
.news ul { margin: 12px 0 0; padding-left: 18px; display: grid; gap: 6px; color: var(--ink-2); font-size: 15px; }
.news-more { display: inline-block; margin-top: 28px; font-weight: 700; }
@media (max-width: 900px) { .news-grid { grid-template-columns: 1fr; } }
</style>"""


def fmt_date(d, lang):
    y, m, dd = (int(x) for x in d.split("-"))
    mon = MONTHS[lang][m - 1]
    return f"{dd}. {mon} {y}" if lang in ("cs", "de") else f"{dd} {mon} {y}"


def anchor(v):
    return "v" + v.replace(".", "-")


def items(entry, lang):
    return "".join(f"<li>{html.escape(x)}</li>" for x in entry[lang])


def build_page(changes, lang, prefix):
    t = TXT[lang]
    shell = (DOCS / prefix / "navod.html").read_text(encoding="utf-8")
    head, _ = shell.split('<div class="layout">', 1)
    head = re.sub(r"<title>.*?</title>", f"<title>{t['title']}</title>", head, count=1)
    head = re.sub(r'<meta name="description" content=".*?">', f'<meta name="description" content="{t["desc"]}">', head, count=1)
    head = head.replace("</style>", PAGE_CSS.strip() + "\n</style>", 1)
    # přepínač jazyků vede na tutéž stránku, přepínač Windows/Mac tu není potřeba
    head = re.sub(r'(<div class="lang"[^>]*>.*?</div>)', lambda m: m.group(1).replace("navod.html", "zmeny.html"), head, count=1, flags=re.S)
    head = re.sub(r'\s*<div class="os".*?</div>', "", head, count=1, flags=re.S)
    toc = "".join(f'<li><a href="#{anchor(c["version"])}">{c["version"]}</a></li>' for c in changes)
    rels = []
    for i, c in enumerate(changes):
        new = f' <span class="new">{t["latest"]}</span>' if i == 0 else ""
        rels.append(f'    <section class="rel" id="{anchor(c["version"])}">\n'
                    f'      <h2>{t["ver"]} {c["version"]} <time datetime="{c["date"]}">{fmt_date(c["date"], lang)}</time>{new}</h2>\n'
                    f'      <ul>{items(c, lang)}</ul>\n    </section>')
    body = f'''<div class="layout clog">
  <nav class="toc" aria-label="{t["toc"]}">
    <p>{t["toc"]}</p>
    <ol>{toc}</ol>
  </nav>

  <article>
    <h1>{t["h1"]}</h1>
    <p class="lede">{t["lede"]}</p>
    <p class="clog-links"><a href="./">{t["home"]}</a><a href="navod.html">{t["guide"]}</a><a href="https://github.com/mhudakcz/Diktovatko_2026/releases">GitHub Releases</a></p>
{chr(10).join(rels)}
  </article>
</div>

<script>
(() => {{
  const links = [...document.querySelectorAll(".toc a")];
  const io = new IntersectionObserver((entries) => {{
    entries.forEach((en) => {{ if (en.isIntersecting) links.forEach((a) => a.classList.toggle("on", a.getAttribute("href") === "#" + en.target.id)); }});
  }}, {{ rootMargin: "-30% 0px -60% 0px" }});
  document.querySelectorAll(".rel").forEach((s) => io.observe(s));
  const bar = document.createElement("div"); bar.className = "progress"; bar.setAttribute("aria-hidden", "true");
  document.body.prepend(bar);
  const upd = () => {{ const d = document.documentElement; bar.style.transform = `scaleX(${{d.scrollTop / Math.max(1, d.scrollHeight - innerHeight)}})`; }};
  addEventListener("scroll", upd, {{ passive: true }}); addEventListener("resize", upd); upd();
}})();
</script>
</body>
</html>
'''
    (DOCS / prefix / "zmeny.html").write_text(head + body, encoding="utf-8")


def build_home(changes, lang, prefix):
    t = TXT[lang]
    p = DOCS / prefix / "index.html"
    s = p.read_text(encoding="utf-8")
    cards = []
    for i, c in enumerate(changes[:3]):
        new = f' <span class="new">{t["latest"]}</span>' if i == 0 else ""
        cards.append(f'        <div class="news reveal" style="--d:{i * 0.1:.1f}s"><h3>{c["version"]} <time datetime="{c["date"]}">{fmt_date(c["date"], lang)}</time>{new}</h3><ul>{items(c, lang)}</ul></div>')
    block = (f'<!-- novinky:start – generuje tools/build_changes.py z docs/changes.json -->\n'
             f'  <section class="block" id="novinky">\n    {HOME_CSS}\n    <div class="wrap">\n'
             f'      <h2 class="reveal">{t["h2"]}</h2>\n      <p class="intro reveal" style="--d:.1s">{t["intro"]}</p>\n'
             f'      <div class="news-grid">\n{chr(10).join(cards)}\n      </div>\n'
             f'      <a class="news-more reveal" href="zmeny.html">{t["more"]}</a>\n    </div>\n  </section>\n  <!-- novinky:end -->')
    if "<!-- novinky:start" in s:
        s = re.sub(r"<!-- novinky:start.*?<!-- novinky:end -->", lambda _: block, s, count=1, flags=re.S)
    else:
        anchor_html = '  <section class="block support" id="podpora">'
        assert s.count(anchor_html) == 1, p
        s = s.replace(anchor_html, "  " + block + "\n" + anchor_html, 1)
    # tečka v ukazateli polohy vpravo
    if '["novinky",' not in s:
        s = s.replace('["podpora",', f'["novinky", "{t["rail"]}"], ["podpora",', 1)
    p.write_text(s, encoding="utf-8")


def main():
    changes = json.loads((DOCS / "changes.json").read_text(encoding="utf-8"))
    for lang, prefix in LANGS.items():
        build_page(changes, lang, prefix)
        build_home(changes, lang, prefix)
    print(f"Historie změn: {len(changes)} verzí, nejnovější {changes[0]['version']}")


if __name__ == "__main__":
    main()
