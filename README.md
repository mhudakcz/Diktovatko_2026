# Diktovátko

**Podržte klávesu, mluvte, pusťte. Text se vloží tam, kde máte kurzor.**

Bezplatná open-source alternativa k [Wispr Flow](https://wisprflow.ai) pro Windows. Funguje v jakékoli aplikaci, třeba ve Slacku, Outlooku, prohlížeči, Teams nebo VS Code. Umí česky i dalších 90+ jazyků.

**[Web projektu](https://mhudakcz.github.io/Diktovatko_2026/)**

![Historie diktování](docs/img/history-light.png)

## Co umí

- **Diktování kamkoliv.** Podržíte pravý Ctrl, mluvíte, pustíte a přepis se vloží do aktivního pole. Schránka se potom vrátí do původního stavu.
- **Indikátor nahrávání.** Dole uprostřed obrazovky se objeví malá „pilulka“. Při nahrávání ukazuje hlasitost vašeho hlasu, při přepisu animaci. Nebere fokus, takže text jde tam, kam má.
- **Ztlumení ostatních zvuků.** Spotify, videa a další aplikace se během nahrávání ztlumí na 10 % a potom vrátí zpátky.
- **Statistiky.** Slova, záznamy, čas mluvení a odhad ušetřeného času za dnešek, týden, měsíc i celkem. K tomu graf posledních 30 dní a přehled, do kterých aplikací diktujete nejvíc.
- **Nastavení v okně.** Zkratka (pravý Ctrl, Ctrl+Win a další nebo vlastní), jazyk, Groq klíč, ztlumení zvuku a automatické spouštění. Změny platí hned bez restartu.
- **Historie.** Každý přepis se uloží lokálně i s časem, aplikací a názvem okna (konverzace, dokument, tiket). Hodí se, když potřebujete zpětně dohledat, na čem jste pracoval. V okně historie jde hledat, filtrovat podle období (dnes, 7/10/14/20/30/90 dní, tento či minulý měsíc, vlastní rozsah) a aplikací, kopírovat a exportovat do Markdownu nebo CSV.
- **Dva způsoby přepisu:**
  - **lokálně a offline** (Whisper large-v3-turbo na CPU), zdarma a nic neopouští počítač,
  - **přes [Groq](https://console.groq.com)** (free tier), přepis trvá kolem 1 sekundy.
- **Ochrana před „halucinacemi“.** Ticho se k přepisu vůbec neposílá a typické vymyšlené věty Whisperu (třeba „Titulky vytvořil…“) se zahodí.

## Instalace

Potřebujete Windows 10/11 a [Python 3.11+](https://www.python.org/downloads/). Při instalaci Pythonu zaškrtněte „Add to PATH“.

1. Stáhněte repozitář (*Code → Download ZIP*) a rozbalte ho.
2. Spusťte `install.bat`.
3. Spusťte `start.bat`. V oznamovací oblasti vedle hodin se objeví ikona mikrofonu.

Při prvním spuštění bez Groq klíče se stáhne model Whisper (~1,6 GB).

Automatické spouštění po přihlášení:

```
powershell -ExecutionPolicy Bypass -File autostart.ps1
```

Odebrání z automatického spouštění: přidejte na konec `-Remove`.

## Používání

| Ikona / pilulka | Stav |
|---|---|
| šedá | načítá se model |
| tmavá | připraveno |
| červená, pilulka se sloupečky | nahrává |
| modrá, pilulka s vlnou | přepisuje |

**Kliknutím na ikonu** otevřete okno s historií, statistikami a nastavením. **Pravým tlačítkem** se dostanete k jednotlivým sekcím, exportu, logu a ukončení.

Když během držení zkratky stisknete jinou klávesu (třeba Ctrl+C), nahrávání se zruší. Běžné zkratky tak fungují dál. Diktovat jde i dlouho, delší nahrávky se pro Groq automaticky rozdělí.

## Nastavení (`config.json`)

Nejjednodušší je nastavovat v okně aplikace (sekce *Nastavení*). Soubor se vytvoří při prvním spuštění a jde upravit i ručně. Změny se projeví do sekundy.

| Klíč | Výchozí | Popis |
|---|---|---|
| `hotkeys` | `["right ctrl"]` | seznam zkratek, např. `"ctrl+windows"`, `"ctrl+alt+space"`, `"scroll lock"` |
| `mode` | `"hold"` | `"hold"` = drž a mluv, `"toggle"` = stisk start, další stisk stop |
| `language` | `"cs"` | kód jazyka, nebo `null` pro automatickou detekci |
| `model` | `"large-v3-turbo"` | lokální model, `small` je rychlejší, ale méně přesný |
| `initial_prompt` | … | nápověda pro model: jména, odborné výrazy, styl |
| `groq_api_key` | `""` | klíč z [console.groq.com](https://console.groq.com), jde nastavit i přes proměnnou `GROQ_API_KEY` |
| `duck_audio` / `duck_level` | `true` / `0.1` | ztlumení ostatních aplikací během nahrávání |
| `overlay` | `true` | plovoucí indikátor nahrávání |
| `history` | `true` | ukládání historie |
| `sounds` | `true` | pípnutí při startu a konci nahrávání |
| `trailing_space` | `true` | mezera za vloženým textem |

## Historie a export

Historie je v souboru `history.db` (SQLite) ve složce aplikace. Export z příkazové řádky:

```
.venv\Scripts\python.exe history.py --month 2026-09
.venv\Scripts\python.exe history.py --from 2026-09-01 --to 2026-09-15 --format csv
.venv\Scripts\python.exe history.py --search "faktura"
```

## Soukromí

- Při lokálním přepisu nic neopouští počítač.
- S Groq klíčem se nahrávka posílá na servery Groq (USA). Text ani historie se nikam neposílají.
- `config.json`, `history.db` a log jsou v `.gitignore`, takže se nedostanou do gitu.
- Historie je uložená jako čitelný text. Když ji nechcete, vypněte ji přes `"history": false`.

## Omezení

- Pouze Windows.
- Do oken spuštěných jako správce se vkládá, jen pokud Diktovátko také běží jako správce.
- Lokální přepis na CPU trvá zhruba 1–1,5× délku nahrávky.

## Struktura

| Soubor | Účel |
|---|---|
| `diktovatko.py` | hlavní aplikace: ikona v liště, zkratka, nahrávání, přepis, vložení textu |
| `overlay.py` | plovoucí indikátor nahrávání |
| `audio_duck.py` | ztlumení ostatních aplikací |
| `history.py` | databáze historie, zjištění aktivního okna, export |
| `app_window.py`, `ui/app.html` | okno s historií, statistikami a nastavením (pywebview) |
| `hotkeys.py` | zkratky: rozlišení levé a pravé klávesy, zrušení při jiné klávese |
| `config.py` | načítání a ukládání nastavení, automatické spouštění |
| `docs/` | propagační stránka (GitHub Pages) |

## Licence

MIT. Autor: Michal Hudák.
