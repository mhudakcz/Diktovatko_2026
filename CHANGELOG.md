# Změny

Číslo verze se posouvá s každou změnou: nová funkce zvýší prostřední číslo, oprava poslední. Verze 1.0.0 bude první, kterou prohlásíme za hotovou.

## 0.12.6 – 2026-09-25

- Web: novinky a historie změn na webu ukazují jen změny v aplikaci, ne úpravy webu a návodu.

## 0.12.5 – 2026-09-25

- Web: kroužící světlo v kartách Offline/Online, Co je nového, Jak pomoct, instalace a v bloku s cenou je o polovinu slabší a dvakrát pomalejší. Panel s přepínačem a sekce Instalace zůstaly beze změny.

## 0.12.4 – 2026-09-25

- Web (CZ, EN, DE): nový úvod – kolem mikrofonu kruhový ekvalizér, měnící se barevný tvar a oběžné dráhy s tečkami, mikrofon jemně dýchá, v pozadí plují abstraktní tvary. Při přehrání ukázky ekvalizér zrychlí a zbarví se.
- Pomalu kroužící světlo i v kartách Offline/Online, Co je nového, Jak pomoct, v kartách instalace a v bloku s cenou (tlumené barvy, každý blok jiným tempem).

## 0.12.3 – 2026-09-25

- Web (CZ, EN, DE): efekty na úvodní stránce – plující barevné záře a zvukové vlny v úvodu, přelévající se barvy v nadpisu, odlesk na žlutých tlačítkách, pomalu kroužící světlo v tmavých panelech. Při omezených animacích v systému se nehýbe nic.

## 0.12.2 – 2026-09-24

- Jazyk aplikace jde přepnout hned vlevo dole v okně (CZ / EN / DE), platí okamžitě. V Nastavení je volba jazyka nahoře a také platí hned.
- Glóbus vedle přepínače jazyka otevře web Diktovátka v jazyce aplikace. V Nastavení → Aktualizace je odkaz na celou historii změn.
- Web (CZ, EN, DE): sekce „Co je nového“ se třemi posledními verzemi a stránka `zmeny.html` se všemi verzemi. Obojí se generuje z `docs/changes.json` skriptem `tools/build_changes.py`.

## 0.12.1 – 2026-09-24

- Okno: přepínač **Cloud · fast / Local · slow** hned v levém panelu, vidět ve všech sekcích. Platí okamžitě a ukáže i přepnutí z indikátoru nebo menu ikony. Bez klíče nabídne jeho vložení.
- Nastavení: přepínač *Přepisovat offline* platí hned, už není potřeba klikat na Uložit.
- Web (CZ, EN, DE): v sekci „Offline, nebo online“ ukázka přepínače **Cloud · fast / Local · slow** z indikátoru, na kterou jde kliknout. Úvod a varování už neradí mazat klíč, ale přepnout na Local · slow.

## 0.12.0 – 2026-09-24

- Aktualizace: před instalací je v Nastavení → Aktualizace přehled změn ze **všech** verzí od té nainstalované, rozdělený po verzích. Položka „Aktualizovat na verzi…“ v menu ikony otevře tenhle přehled, instaluje se až tlačítkem. Oznámení říká, kolik verzí vyšlo.
- Indikátor je napůl průhledný (70 %), pod myší se zobrazí celý.
- Indikátor jde myší přetáhnout kamkoli na obrazovku, poloha se pamatuje (`overlay_pos`). Dvojklik ho vrátí dole doprostřed.

## 0.11.1 – 2026-09-24

- Oprava: po přepnutí Cloud / Local během nahrávání aplikace nepoznala puštění zkratky a nahrávala dál. Uložení nastavení teď drženou zkratku nezruší, pokud se zkratky nezměnily.
- Štítek v indikátoru má piktogramy: blesk u **Cloud · fast**, šnek u **Local · slow**.

## 0.11.0 – 2026-09-24

- Přepínání Cloud / Local bez mazání klíče: v indikátoru při diktování je vpravo štítek **Cloud · fast** (Groq) nebo **Local · slow** (v počítači). Kliknutím myší se přepne, a to hned pro nahrávku, která právě běží. Okno přitom nevezme fokus.
- Totéž v menu ikony (*Přepisovat offline*) a v Nastavení → Přepis. Nová volba `offline` v `config.json`.
- Na Macu se štítek zatím jen zobrazuje, přepíná se v menu ikony.

## 0.10.2 – 2026-09-24

- Návod (CZ, EN, DE): doporučený krok zapnout v účtu Groq Zero Data Retention a přesnější popis, co se s nahrávkou u Groq děje (nezveřejňuje se, netrénuje se na ní, bez ZDR se výjimečně uchová až 30 dní).
- Web: v porovnání offline/online bod o Zero Data Retention.

## 0.10.1 – 2026-09-24

- Kontrola aktualizací běží jednou za 2 hodiny (dřív 6).
- Web (CZ, EN, DE): mezi funkcemi karta „Aktualizuje se samo“.

## 0.10.0 – 2026-09-24

- Automatické aktualizace: aplikace jednou za 6 hodin zkontroluje GitHub Releases, při nové verzi zobrazí upozornění a v menu ikony i v Nastavení → Aktualizace nabídne „Aktualizovat“. Aktualizace stáhne novou verzi, ponechá nastavení, klíč i historii, doinstaluje nové knihovny a aplikaci restartuje.
- Nastavení → Aktualizace: nainstalovaná verze, popis novinek, tlačítka Zkontrolovat a Aktualizovat teď, volba automatické kontroly.
- Vývojová kopie z gitu se aktualizací nepřepisuje.

## 0.9.2 – 2026-09-24

- Žluté tlačítko „☕ Podpořit“ v horní liště všech stránek (web i návod, CZ, EN, DE) vede rovnou na Ko-fi. Je vidět i na telefonu.

## 0.9.1 – 2026-09-24

- Možnost podpořit projekt: sekce „Podpořit“ s odkazem na Ko-fi na webu (CZ, EN, DE), odkaz v menu webu, položka „Podpořit projekt ☕“ v menu ikony aplikace a sekce v README.
- Log u nahrávky bez řeči uvádí naměřenou hlasitost (špička a RMS), aby šlo poznat, jestli je problém v mikrofonu.

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
