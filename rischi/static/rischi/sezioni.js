/* Sezioni apribili in tutte le pagine: la fascia del titolo (legend dei moduli, h2 dei riquadri) apre e chiude
   la sezione (anche i gruppi di schede per modulo). Nella libreria (amministrazione) valgono per i riquadri dei campi,
   le righe collegate e i gruppi della pagina iniziale; lì alla prima visita sono tutte aperte. Alla prima visita è aperta solo la prima sezione (e quelle con errori o con il collegamento della
   pagina, es. #funzioni); poi la pagina ricorda lo stato scelto. Le sezioni già richiudibili (details) restano come sono. */
(function () {
  "use strict";

  const CHIAVE = "sezioni:" + location.pathname;

  function leggiStato() {
    try { return JSON.parse(localStorage.getItem(CHIAVE) || "null"); } catch (e) { return null; }
  }

  function salvaStato(sezioni) {
    try { localStorage.setItem(CHIAVE, JSON.stringify(sezioni.map((s) => !s.classList.contains("chiusa")))); } catch (e) { /* senza memoria */ }
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

    const ricordato = leggiStato();
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
      let aperta = ricordato && ricordato.length === sezioni.length ? ricordato[i] : libreria || i === 0;
      if (sezione.querySelector(".errorlist, .errore, .errors")) aperta = true;
      if (bersaglio && (sezione === bersaglio || sezione.contains(bersaglio))) aperta = true;
      imposta(sezione, aperta);
      const cambia = function (e) {
        if (e && e.target.closest && e.target.closest("a")) return; // il nome del gruppo nella libreria resta un collegamento
        imposta(sezione, sezione.classList.contains("chiusa"));
        salvaStato(sezioni);
      };
      t.addEventListener("click", cambia);
      t.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); cambia(); }
      });
    });

    // Pulsanti per aprire o chiudere tutto, sopra la prima sezione
    const comandi = document.createElement("p");
    comandi.className = "comandi-sezioni";
    [["apri", "Apri tutte le sezioni"], ["chiudi", "Chiudi tutte"]].forEach(function ([azione, testo]) {
      const b = document.createElement("button");
      b.type = "button";
      if (libreria) b.className = "button";
      b.textContent = testo;
      b.addEventListener("click", function () {
        sezioni.forEach((s) => imposta(s, azione === "apri"));
        salvaStato(sezioni);
      });
      comandi.appendChild(b);
      comandi.appendChild(document.createTextNode(" "));
    });
    const primo = sezioni[0].closest("form.modulo, .modulo") || sezioni[0];
    primo.parentNode.insertBefore(comandi, primo);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", prepara);
  else prepara();
})();
