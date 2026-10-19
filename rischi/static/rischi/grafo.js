/* PLr e grafo del rischio in diretta mentre si scelgono S, F e P (radio della funzione in commessa o menu della
   funzione tipo nella libreria). Stessa tabella di models.plr e di engine.js (EN ISO 13849-1, fig. A.1). */
(function () {
  "use strict";

  function valore(nome) {
    const scelto = document.querySelector(`input[name="${nome}"]:checked`) || document.querySelector(`select[name="${nome}"]`);
    return scelto ? scelto.value : "";
  }

  function aggiorna() {
    const s = valore("s"), f = valore("f"), p = valore("p");
    const plr = document.getElementById("plr");
    if (plr) {
      plr.textContent = s && f && p
        ? ["a", "b", "b", "c", "c", "d", "d", "e"][(s === "S2" ? 4 : 0) + (f === "F2" ? 2 : 0) + (p === "P2" ? 1 : 0)]
        : "–";
    }
    // Percorso evidenziato: i rami il cui codice è l'inizio della scelta (S, poi S+F, poi S+F+P)
    const scelta = s ? s + (f ? f + (p || "") : "") : "";
    document.querySelectorAll(".grafo-plr [data-chiave]").forEach((g) => {
      const k = g.dataset.chiave;
      g.classList.toggle("attivo", g.classList.contains("foglia") ? k === scelta : scelta.startsWith(k));
    });
  }

  document.addEventListener("change", (e) => { if (["s", "f", "p"].includes(e.target.name)) aggiorna(); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", aggiorna);
  else aggiorna();
})();
