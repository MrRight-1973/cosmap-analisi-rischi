/* Sezioni apribili in tutte le pagine: la fascia del titolo (legend dei moduli, h2 dei riquadri) apre e chiude
   la sezione (anche i gruppi di schede per modulo). Nella libreria (amministrazione) valgono per i riquadri dei campi,
   le righe collegate e i gruppi della pagina iniziale; lì alla prima visita sono tutte aperte. Alla prima visita è aperta solo la prima sezione (e quelle con errori o con il collegamento della
   pagina, es. #funzioni); poi la pagina ricorda lo stato scelto. Le sezioni già richiudibili (details) restano come sono. */
(function () {
  "use strict";

  const CHIAVE = "sezioni:" + location.pathname;
  const CHIAVE_GRUPPI = "sezioni:gruppi-libreria"; // pagina iniziale della libreria e barra delle pagine interne

  function leggiStato(chiave) {
    try { return JSON.parse(localStorage.getItem(chiave) || "null"); } catch (e) { return null; }
  }

  function salvaStato(chiave, sezioni) {
    try { localStorage.setItem(chiave, JSON.stringify(sezioni.map((s) => !s.classList.contains("chiusa")))); } catch (e) { /* senza memoria */ }
  }

  function titolo(sezione) {
    return sezione.querySelector(":scope > legend, :scope > h2, :scope > table > caption");
  }

  function imposta(sezione, aperta) {
    sezione.classList.toggle("chiusa", !aperta);
    titolo(sezione).setAttribute("aria-expanded", aperta ? "true" : "false");
  }

  function prepara() {
    const libreria = !!document.getElementById("content-main");
    const SELETTORE = libreria
      ? "#content-main fieldset.module, #content-main div.module"
      : ".modulo fieldset, section.riquadro, section.modulo-gruppo";
    if (libreria) {
      // Il riquadro principale dei campi non ha titolo: gliene diamo uno se nella pagina ci sono altre sezioni
      const senzaTitolo = Array.from(document.querySelectorAll("#content-main fieldset.module")).filter(
        (f) => !f.closest(".inline-group") && !titolo(f) && !f.querySelector("details"));
      const titolate = document.querySelectorAll("#content-main fieldset.module > h2, #content-main .inline-group fieldset.module > h2");
      if (senzaTitolo.length && titolate.length) {
        senzaTitolo.forEach(function (f) {
          const h = document.createElement("h2");
          h.className = "fieldset-heading";
          h.textContent = "Dati principali";
          f.insertBefore(h, f.firstChild);
        });
      }
    }
    const sezioni = Array.from(document.querySelectorAll(SELETTORE)).filter(function (s) {
      const contenitore = s.parentElement && s.parentElement.closest(SELETTORE);
      return titolo(s) && !s.querySelector("details.sezione") && !(contenitore && titolo(contenitore));
    });
    if (sezioni.length < 2) return;

    const chiave = document.body.classList.contains("dashboard") ? CHIAVE_GRUPPI : CHIAVE;
    rendiApribili(sezioni, chiave, libreria, sezioni[0].closest("form.modulo, .modulo") || sezioni[0], function () { return libreria; });
  }

  // Elenco dei gruppi della libreria a sinistra nelle pagine interne: uguale alla pagina iniziale (stessi
  // gruppi richiudibili, stato condiviso), con evidenziata la voce aperta e il suo gruppo sempre aperto
  function preparaBarra() {
    const barra = document.getElementById("nav-sidebar");
    if (!barra) return;
    const gruppi = Array.from(barra.querySelectorAll("div.module")).filter((g) => titolo(g));
    if (!gruppi.length) return;
    rendiApribili(gruppi, CHIAVE_GRUPPI, true, gruppi[0], function () { return true; },
      function (g) { return g.classList.contains("current-app"); });
  }

  function rendiApribili(sezioni, chiave, libreria, primo, apertaDiBase, forzaAperta) {
    const ricordato = leggiStato(chiave);
    const bersaglio = location.hash ? document.getElementById(location.hash.slice(1)) : null;
    sezioni.forEach(function (sezione, i) {
      const t = titolo(sezione);
      sezione.classList.add("sezione-apribile");
      if (t.tagName === "CAPTION") sezione.classList.add("titolo-in-tabella");
      t.setAttribute("role", "button");
      t.setAttribute("tabindex", "0");
      const segno = document.createElement("span");
      segno.className = "segno-sezione";
      t.appendChild(segno);
      let aperta = ricordato && ricordato.length === sezioni.length ? ricordato[i] : apertaDiBase(sezione) || i === 0;
      if (sezione.querySelector(".errorlist, .errore, .errors")) aperta = true;
      if (bersaglio && (sezione === bersaglio || sezione.contains(bersaglio))) aperta = true;
      if (forzaAperta && forzaAperta(sezione)) aperta = true;
      imposta(sezione, aperta);
      const cambia = function (e) {
        if (e && e.target.closest && e.target.closest("a")) return; // il nome del gruppo nella libreria resta un collegamento
        imposta(sezione, sezione.classList.contains("chiusa"));
        salvaStato(chiave, sezioni);
      };
      t.addEventListener("click", cambia);
      t.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); cambia(); }
      });
    });

    // Pulsanti per aprire o chiudere tutto, sopra la prima sezione (solo nelle pagine delle commesse)
    if (libreria) return;
    const comandi = document.createElement("p");
    comandi.className = "comandi-sezioni";
    [["apri", "Apri tutte le sezioni"], ["chiudi", "Chiudi tutte"]].forEach(function ([azione, testo]) {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = testo;
      b.addEventListener("click", function () {
        sezioni.forEach((s) => imposta(s, azione === "apri"));
        salvaStato(chiave, sezioni);
      });
      comandi.appendChild(b);
      comandi.appendChild(document.createTextNode(" "));
    });
    primo.parentNode.insertBefore(comandi, primo);
  }

  // Percorso nelle pagine della libreria: la prima voce si chiama come nel menu ("Libreria e utenti") e la voce
  // dell'applicazione (Libreria, Autenticazione…) sparisce, perché porterebbe alla stessa pagina iniziale.
  function sistemaPercorso() {
    const percorso = document.querySelector(".breadcrumbs");
    const inizio = percorso && percorso.querySelector("a");
    if (!inizio || inizio.textContent.trim() !== "Pagina iniziale") return;  // "Home" dell'amministrazione
    inizio.textContent = "Libreria e utenti";
    const seconda = inizio.nextElementSibling;
    const resto = seconda && seconda.tagName === "A" && seconda.pathname.startsWith(inizio.pathname)
      ? seconda.pathname.slice(inizio.pathname.length).replace(/\/$/, "") : null;
    if (resto && !resto.includes("/")) {  // es. /admin/rischi/: pagina dell'applicazione
      const separatore = seconda.previousSibling;
      if (separatore && separatore.nodeType === Node.TEXT_NODE) separatore.remove();
      seconda.remove();
    }
  }

  function avvia() {
    sistemaPercorso();
    prepara();
    preparaBarra();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", avvia);
  else avvia();
})();
