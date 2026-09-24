# Změny

Číslo verze se posouvá s každou změnou: nová funkce zvýší prostřední číslo, oprava poslední. Verze 1.0.0 bude první, kterou prohlásíme za hotovou.

## 0.9.0 – 2026-09-24

Bezpečnostní audit a revize kódu.

**Bezpečnost a soukromí**
- Groq klíč je v systémovém trezoru hesel (Windows Správce přihlašovacích údajů, macOS Klíčenka), ne v `config.json`. Stávající klíč se přesune automaticky. Do okna aplikace se klíč neposílá.
- Log neobsahuje nadiktovaný text a rotuje se (max. 3 × 1 MB).
- Schránka se obnoví až po vložení a jen tehdy, když v ní je pořád náš text. Obrázek nebo soubor ve schránce se nepřepíše prázdným textem.
- Když uživatel během přepisu přepne okno, text se nevloží do jiného okna, ale zůstane ve schránce s upozorněním.
- Nadiktovaný text se ve Windows neukládá do historie schránky (Win+V) ani do cloudové schránky. Na Macu je označený jako dočasný.
- Okno aplikace: bezpečnostní pravidla CSP, žádné písmo z Googlu, otevřít jde jen stránka Groq s klíči, export přijme jen MD a CSV.
- CSV export je chráněný proti spuštění vzorců z názvů oken v Excelu.
- Historie: mazání vybraných záznamů i celé historie, automatické mazání starších záznamů, volba neukládat názvy oken.
- Kontrola všech hodnot nastavení, zamčené verze závislostí, instalátory kontrolují verzi Pythonu.
- Na Macu mají `config.json`, `history.db` a log práva jen pro vlastníka.

**Spolehlivost a výkon**
- Stisky zkratek se zpracovávají v jednom vlákně v pořadí, takže se po rychlém ťuknutí nezasekne mikrofon. Ve Windows se ověřuje skutečný stav kláves (po zamčení počítače už nespustí nahrávání samotný Ctrl).
- Změny nastavení a přepnutí mezi Groq a lokálním modelem jsou ošetřené proti souběhu.
- Ztlumené aplikace se po pádu při dalším startu vrátí na původní hlasitost.
- Srozumitelné hlášky při chybě mikrofonu, neplatném klíči, limitu Groq nebo výpadku internetu. Nahrávání se po 15 minutách ukončí samo.
- Statistiky počítá databáze (sloupec `words`), databáze v režimu WAL, hledání bez ohledu na velikost písmen i s diakritikou.
- Indikátor vykresluje úsporněji (2× převzorkování, 24 snímků/s). Spojení ke Groq se používá opakovaně.
- Filtr vymyšlených vět zahodí jen přepis, který je celý vymyšlený. Běžné věty s „děkuji za pozornost“ projdou.
- Odstraněn zastaralý `autostart.ps1` (automatické spouštění je v nastavení).

## 0.8.2 – 2026-09-24

- Web: výrazný štítek „0 Kč měsíčně. Bez předplatného, napořád.“ hned nad nadpisem na první obrazovce (CZ, EN, DE).

## 0.8.1 – 2026-09-24

- Web (CZ, EN, DE): zdůraznění, že jde o alternativu bez měsíčních poplatků (řádek v úvodu a sekce „0 Kč měsíčně“).
- Nová sekce o rychlém přepisu: proč je potřeba klíč, postup, jak ho získat a vložit do aplikace, s náhledem nastavení.
- Nová sekce „Offline, nebo online“ s varováním, že v online režimu odchází nahrávka na servery Groq v USA.

## 0.8.0 – 2026-09-24

- Jazykové verze: aplikace (okno, menu ikony, indikátor, export) v češtině, angličtině a němčině. Volba „Jazyk aplikace“ v nastavení, výchozí je čeština.
- Web a návod v angličtině (`docs/en/`) a němčině (`docs/de/`) s přepínačem CZ/EN/DE. Ukázka na webu mluví anglicky, případně německy.
- Návod má design hlavní stránky (varianta 2) a pruh průběhu čtení.
- Oprava: v návodu se v režimu Windows zobrazoval i krok určený pro Mac.

## 0.7.2 – 2026-09-24

- Web na telefonu: mikrofon v úvodu už se nesmrskne, nadpisy Windows/Mac se nelámou, nahoře zůstává tlačítko Návod.
- Úvod webu zmiňuje, že jde o bezplatnou alternativu k Wispr Flow (v aplikaci ani v nastavení tato zmínka není).

## 0.7.1 – 2026-09-24

- Varianta 2 webu je teď hlavní stránka. Stará adresa `v2.html` přesměruje na hlavní stránku, původní varianta zůstává jen v historii gitu.

## 0.7.0 – 2026-09-24

- Nová varianta webu (`docs/v2.html`): ukázka diktování řízená rolováním, animace při rolování, mikrofon, který po kliknutí promluví, běžící pás aplikací.
- Ukazatel polohy na stránce: svislá dráha se sekcemi a procenty vpravo, pruh nahoře.
- Ukázková věta bez anglických slov („testovací web“ místo „staging“), i na snímcích obrazovky.
- Číslo verze v aplikaci (menu ikony, okno, log), na webu a v README, tento přehled změn.

## 0.6.0 – 2026-09-24

- Nový design webu: celoplošný úvod s nahrávací scénou a ukázkou vkládání do skutečného vstupního pole.
- Ukázka umí mluvit česky (syntéza řeči prohlížeče), žluté tlačítko zvuku.
- Výchozí zkratka Ctrl + Win, na Macu Ctrl + ⌘. Z nastavení zmizely zmínky o Wispr Flow.

## 0.5.0 – 2026-09-24

- Podrobnější návod pro Mac: Gatekeeper, oprávnění krok za krokem, Fn, mikrofon, řešení problémů.
- Souhrn „Ve zkratce“ a rozcestník na webu, v návodu i v README.
- Tlačítka ke stažení s logem Windows a Macu.

## 0.4.0 – 2026-09-24

- Mac verze (`platform_mac.py`, `install.command`, `start.command`).
- Návod pro laiky `docs/navod.html`, včetně vytvoření vlastního Groq klíče.
- Na webu sekce o úspoře času s kalkulačkou.
- Okno: svislé menu sekcí, zkratka jako výběr s volbou Vlastní, viditelné potvrzení uložení nastavení.

## 0.3.0 – 2026-09-24

- Jedno okno s historií, statistikami a nastavením.
- Statistiky: slova, čas mluvení, ušetřený čas, graf 30 dní, top aplikace.
- Vlastní obsluha zkratek: rozliší levý a pravý Ctrl, zruší nahrávání při jiné klávese (Ctrl+C).
- Období 10/14/20/30 dní a vlastní rozsah v historii a exportu. Dlouhé nahrávky se pro Groq dělí.

## 0.2.0 – 2026-09-24

- Propagační web na GitHub Pages.

## 0.1.0 – 2026-09-24

- První verze: diktování podržením klávesy, přepis lokálně nebo přes Groq, vložení na místo kurzoru.
- Plovoucí indikátor nahrávání, ztlumení ostatních aplikací, lokální historie s cílovým oknem a export.
- Filtr ticha a typických halucinací Whisperu.
