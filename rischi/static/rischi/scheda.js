/* Scheda (modello e della commessa): grassetto nei testi, norme a comparsa, sezioni richiudibili. */
(function () {
  "use strict";

  // Grassetto: il pulsante G racchiude il testo selezionato tra ** e **; nel PDF esce in grassetto.
  function aggiungiGrassetto(area) {
    const pulsante = document.createElement("button");
    pulsante.type = "button";
    pulsante.className = "pulsante-grassetto";
    pulsante.title = "Grassetto: seleziona il testo e premi G (nel PDF esce in grassetto)";
    pulsante.innerHTML = "<b>G</b>";
    pulsante.addEventListener("click", function () {
      const inizio = area.selectionStart, fine = area.selectionEnd;
      const scelto = area.value.slice(inizio, fine) || "testo";
      area.setRangeText("**" + scelto + "**", inizio, fine, "select");
      area.setSelectionRange(inizio + 2, inizio + 2 + scelto.length);
      area.focus();
      area.dispatchEvent(new Event("input", { bubbles: true }));
    });
    area.parentNode.insertBefore(pulsante, area);
  }

  // Norme: compaiono quelle compilate più una vuota; scegliendo una norma si apre la successiva.
  function preparaNorme() {
    const scelte = Array.from(document.querySelectorAll("select[name^='norma_']"))
      .filter((s) => /^norma_\d+$/.test(s.name))
      .sort((a, b) => parseInt(a.name.slice(6)) - parseInt(b.name.slice(6)));
    if (!scelte.length) return;
    const riga = (s) => s.closest(".form-row, .campo") || s;
    function aggiorna() {
      let ultima = -1;
      scelte.forEach((s, i) => { if (s.value) ultima = i; });
      scelte.forEach((s, i) => { riga(s).hidden = i > ultima + 1; });
    }
    scelte.forEach((s) => s.addEventListener("change", aggiorna));
    aggiorna();
  }

  // Sezioni: si aprono quelle con errori; pulsanti per aprirle o chiuderle tutte.
  function preparaSezioni() {
    const sezioni = document.querySelectorAll("details.sezione");
    sezioni.forEach((d) => { if (d.querySelector(".errorlist, .errors")) d.open = true; });
    document.querySelectorAll("[data-sezioni]").forEach((b) => b.addEventListener("click", function () {
      const apri = b.dataset.sezioni === "apri";
      sezioni.forEach((d) => { d.open = apri; });
    }));
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form textarea").forEach(aggiungiGrassetto);
    preparaNorme();
    preparaSezioni();
  });
})();
