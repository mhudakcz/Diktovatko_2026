# Změny

Číslo verze se posouvá s každou změnou: nová funkce zvýší prostřední číslo, oprava poslední. Verze 1.0.0 bude první, kterou prohlásíme za hotovou.

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
