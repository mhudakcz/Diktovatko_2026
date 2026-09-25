/* Google Analytics jen se souhlasem návštěvníka.
   Dokud návštěvník nepovolí, gtag.js se vůbec nenačte a nic se neposílá.
   Volba se pamatuje v localStorage ("diktovatko-consent": "yes" / "no"),
   odkaz s atributem data-consent (v patičce) lištu otevře znovu. */
(() => {
  const ID = "G-BMP38THJWD", KEY = "diktovatko-consent";
  const T = {
    cs: { text: "Web používá Google Analytics, abych věděl, kolik lidí ho navštěvuje a co je zajímá. Aplikace Diktovátko sama nic takového nesleduje.", yes: "Povolit", no: "Nepovolit", settings: "Nastavení cookies" },
    en: { text: "This website uses Google Analytics so I know how many people visit and what they find interesting. The Diktovátko app itself tracks nothing like this.", yes: "Allow", no: "Decline", settings: "Cookie settings" },
    de: { text: "Diese Website nutzt Google Analytics, damit ich weiß, wie viele Menschen sie besuchen und was sie interessiert. Die App Diktovátko selbst verfolgt nichts dergleichen.", yes: "Erlauben", no: "Ablehnen", settings: "Cookie-Einstellungen" },
  };
  const t = T[(document.documentElement.lang || "cs").slice(0, 2)] || T.cs;
  const get = () => { try { return localStorage.getItem(KEY); } catch (e) { return null; } };
  const set = (v) => { try { localStorage.setItem(KEY, v); } catch (e) {} };

  let loaded = false;
  function load() {
    if (loaded) return;
    loaded = true;
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { dataLayer.push(arguments); };
    gtag("js", new Date());
    gtag("config", ID);
    const s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + ID;
    document.head.append(s);
  }
  function revoke() {
    // Po odvolání souhlasu smažeme cookies Analytics (_ga, _ga_…) a zastavíme další měření.
    window["ga-disable-" + ID] = true;
    document.cookie.split(";").map((c) => c.split("=")[0].trim()).filter((n) => /^_ga/.test(n)).forEach((n) => {
      const host = location.hostname;
      for (const d of ["", host, "." + host]) document.cookie = n + "=; Max-Age=0; path=/" + (d ? "; domain=" + d : "");
    });
  }

  const css = `
.dk-consent { position: fixed; z-index: 90; left: 16px; bottom: 16px; width: min(420px, calc(100vw - 32px)); padding: 16px 18px; border-radius: 16px;
  background: #1A1446; color: #EDEBFF; border: 1px solid rgb(185 179 255 / .28); box-shadow: 0 24px 60px -20px rgb(0 0 0 / .55);
  font: 14px/1.5 "Onest", "Segoe UI", system-ui, sans-serif; animation: dkIn .35s ease-out both; }
.dk-consent p { margin: 0 0 12px; }
.dk-consent .row { display: flex; gap: 10px; flex-wrap: wrap; }
.dk-consent button { border: 0; border-radius: 999px; padding: 8px 16px; font: 600 14px/1 inherit; font-family: inherit; cursor: pointer; }
.dk-consent .yes { background: #FFD23F; color: #16133A; }
.dk-consent .no { background: rgb(255 255 255 / .1); color: #EDEBFF; }
.dk-consent button:focus-visible { outline: 2px solid #FFD23F; outline-offset: 2px; }
@keyframes dkIn { from { opacity: 0; transform: translateY(10px); } }
@media (prefers-reduced-motion: reduce) { .dk-consent { animation: none; } }`;

  function banner() {
    if (document.querySelector(".dk-consent")) return;
    if (!document.getElementById("dk-consent-css")) {
      const st = document.createElement("style"); st.id = "dk-consent-css"; st.textContent = css; document.head.append(st);
    }
    const box = document.createElement("div");
    box.className = "dk-consent"; box.setAttribute("role", "dialog"); box.setAttribute("aria-label", t.settings);
    box.innerHTML = `<p></p><div class="row"><button type="button" class="yes"></button><button type="button" class="no"></button></div>`;
    box.querySelector("p").textContent = t.text;
    box.querySelector(".yes").textContent = t.yes;
    box.querySelector(".no").textContent = t.no;
    box.querySelector(".yes").onclick = () => { set("yes"); box.remove(); window["ga-disable-" + ID] = false; load(); };
    box.querySelector(".no").onclick = () => { set("no"); box.remove(); revoke(); };
    document.body.append(box);
  }

  const start = () => {
    document.querySelectorAll("[data-consent]").forEach((a) => {
      a.textContent = t.settings;
      a.addEventListener("click", (e) => { e.preventDefault(); banner(); });
    });
    const v = get();
    if (v === "yes") load();
    else if (v !== "no") banner();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
