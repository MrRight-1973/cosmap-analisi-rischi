/* Scheda (modello e della commessa): testi formattati, norme a comparsa, sezioni richiudibili. */
(function () {
  "use strict";

  // Testi formattati: al posto della casella di testo c'è un piccolo editor (grassetto, corsivo,
  // sottolineato, elenchi). Il copia/incolla da Word o da altre pagine mantiene questi formati e
  // scarta il resto. La casella nascosta riceve un HTML ridotto, che il PDF riproduce.
  const TAG_EDITOR = /<\/?(b|strong|i|em|u|br|p|div|ul|ol|li|span)\b[^>]*>/i;
  const BLOCCHI = /^(P|DIV|H[1-6]|BLOCKQUOTE|PRE|TABLE|TR|SECTION|ARTICLE|HEADER|FOOTER|ADDRESS|DL|DT|DD|FIGURE)$/;
  const SALTATI = /^(SCRIPT|STYLE|HEAD|TITLE|META|LINK|TEMPLATE|XML|IMG|SVG|OBJECT|IFRAME|INPUT|BUTTON|SELECT|TEXTAREA)$/;
  const FINE_RIGA = /(<br>|<ul>|<ol>|<li>|<\/li>|<\/ul>|<\/ol>)$/;

  function esc(testo) {
    return testo.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function formati(el) {
    const tag = el.tagName;
    const stile = (el.getAttribute("style") || "").replace(/\s/g, "").toLowerCase();
    const peso = (stile.match(/font-weight:(\w+)/) || [])[1];
    let grassetto = /^(B|STRONG|H[1-6])$/.test(tag) && !/^(normal|[1-4]00)$/.test(peso || "");
    grassetto = grassetto || /^(bold|bolder|[6-9]00)$/.test(peso || "");
    const corsivo = tag === "I" || tag === "EM" || stile.includes("font-style:italic");
    const sottolineato = tag === "U" || /text-decoration[^;]*underline/.test(stile);
    return [grassetto && "b", corsivo && "i", sottolineato && "u"].filter(Boolean);
  }

  // HTML qualsiasi (Word, pagine web, l'editor stesso) -> HTML ridotto.
  function pulisci(html) {
    const doc = new DOMParser().parseFromString(html, "text/html");
    let out = "";
    const aCapo = () => { if (out && !FINE_RIGA.test(out)) out += "<br>"; };
    function visita(nodo) {
      nodo.childNodes.forEach(function (n) {
        if (n.nodeType === Node.TEXT_NODE) {
          let t = n.data.replace(/[ \t\r\n]+/g, " ");
          if (!out || FINE_RIGA.test(out)) t = t.replace(/^ +/, "");
          out += esc(t);
        } else if (n.nodeType === Node.ELEMENT_NODE) {
          elemento(n);
        }
      });
    }
    function elemento(el) {
      const tag = el.tagName.toUpperCase();
      if (SALTATI.test(tag) || tag.includes(":")) return;
      const stile = (el.getAttribute("style") || "").replace(/\s/g, "").toLowerCase();
      if (stile.includes("mso-list:ignore")) return;  // punto o numero dell'elenco di Word (sotto)
      if (/mso-list:l\d/.test(stile) && BLOCCHI.test(tag)) {  // paragrafo di un elenco di Word
        const segno = el.querySelector("[style*='mso-list']");
        const tipo = segno && /^\w{1,3}[.)]$/.test(segno.textContent.replace(/\s/g, "")) ? "ol" : "ul";
        const chiusura = "</" + tipo + ">";
        if (out.endsWith(chiusura)) out = out.slice(0, -chiusura.length);  // continua l'elenco precedente
        else out = out.replace(/(<br>)+$/, "") + "<" + tipo + ">";
        out += "<li>";
        visita(el);
        out = out.replace(/(<br>)+$/, "") + "</li>" + chiusura;
        return;
      }
      if (tag === "BR") { out += "<br>"; return; }
      if (tag === "UL" || tag === "OL") {
        out = out.replace(/(<br>)+$/, "");
        out += "<" + tag.toLowerCase() + ">";
        visita(el);
        out += "</" + tag.toLowerCase() + ">";
        return;
      }
      if (tag === "LI") {
        out = out.replace(/(<br>)+$/, "");
        out += "<li>";
        visita(el);
        out = out.replace(/(<br>)+$/, "") + "</li>";
        return;
      }
      const blocco = BLOCCHI.test(tag);
      if (blocco) aCapo();
      const tags = formati(el);
      out += tags.map((t) => "<" + t + ">").join("");
      visita(el);
      out += tags.reverse().map((t) => "</" + t + ">").join("");
      if (tag === "TD" || tag === "TH") out += " ";
      if (blocco) aCapo();
    }
    visita(doc.body);
    let prima;
    do {  // via i formati vuoti e gli a capo in fondo
      prima = out;
      out = out.replace(/<(b|i|u)><\/\1>/g, "").replace(/(<br>|\s)+$/, "");
    } while (out !== prima);
    const vuoto = !out.replace(/<[^>]*>/g, "").replace(/&nbsp;| |\s/g, "") && !out.includes("<li>");
    return vuoto ? "" : out;
  }

  // Valore della casella -> contenuto dell'editor (anche i testi scritti prima, con **grassetto**).
  function inEditor(valore) {
    if (TAG_EDITOR.test(valore)) return pulisci(valore);
    return esc(valore).replace(/\*\*([\s\S]+?)\*\*/g, "<b>$1</b>").replace(/\r?\n/g, "<br>");
  }

  const COMANDI = [
    ["bold", "<b>G</b>", "Grassetto (Ctrl+G)"],
    ["italic", "<i>C</i>", "Corsivo (Ctrl+I)"],
    ["underline", "<u>S</u>", "Sottolineato (Ctrl+S)"],
    ["insertUnorderedList", "• Elenco", "Elenco puntato"],
    ["insertOrderedList", "1. Elenco", "Elenco numerato"],
    ["removeFormat", "Togli formato", "Toglie grassetto, corsivo e sottolineato dal testo selezionato"],
  ];
  const SCORCIATOIE = { g: "bold", b: "bold", i: "italic", s: "underline", u: "underline" };

  function preparaEditor(area) {
    if (area.dataset.editor || area.name.includes("__prefix__")) return;
    area.dataset.editor = "1";
    const bloccato = area.disabled || area.readOnly;
    const contenitore = document.createElement("div");
    contenitore.className = "testo-ricco" + (bloccato ? " bloccato" : "");
    const barra = document.createElement("div");
    barra.className = "barra-testo";
    const editor = document.createElement("div");
    editor.className = "editor-testo";
    editor.contentEditable = bloccato ? "false" : "true";
    editor.setAttribute("role", "textbox");
    editor.setAttribute("aria-multiline", "true");
    editor.style.minHeight = (Math.min(Math.max(parseInt(area.getAttribute("rows")) || 2, 2), 5) * 1.5) + "em";
    editor.innerHTML = inEditor(area.value);
    const etichetta = area.id && document.querySelector("label[for='" + area.id + "']");
    if (etichetta) {
      editor.setAttribute("aria-label", etichetta.textContent);
      etichetta.addEventListener("click", () => editor.focus());
    }

    function aggiorna() {
      area.value = pulisci(editor.innerHTML);
      area.dispatchEvent(new Event("input", { bubbles: true }));
    }
    function esegui(comando) {
      editor.focus();
      document.execCommand("styleWithCSS", false, false);
      document.execCommand(comando, false, null);
      aggiorna();
    }
    COMANDI.forEach(function ([comando, testo, titolo]) {
      const b = document.createElement("button");
      b.type = "button";
      b.innerHTML = testo;
      b.title = titolo;
      b.addEventListener("mousedown", (e) => e.preventDefault());  // la selezione resta nel testo
      b.addEventListener("click", () => esegui(comando));
      barra.appendChild(b);
    });

    editor.addEventListener("input", aggiorna);
    editor.addEventListener("blur", aggiorna);
    editor.addEventListener("keydown", function (e) {
      const comando = (e.ctrlKey || e.metaKey) && !e.altKey && !e.shiftKey && SCORCIATOIE[e.key.toLowerCase()];
      if (comando) {
        e.preventDefault();
        esegui(comando);
      }
    });
    editor.addEventListener("paste", function (e) {
      if (!e.clipboardData) return;
      e.preventDefault();
      const html = e.clipboardData.getData("text/html");
      const pezzo = html ? pulisci(html) : inEditor(e.clipboardData.getData("text/plain")).replace(/\*\*/g, "");
      document.execCommand("insertHTML", false, pezzo || "");
      aggiorna();
    });
    editor.addEventListener("drop", function (e) {
      if (!e.dataTransfer || !e.dataTransfer.getData("text/html")) return;
      e.preventDefault();
      const pezzo = pulisci(e.dataTransfer.getData("text/html"));
      if (document.caretRangeFromPoint) {
        const punto = document.caretRangeFromPoint(e.clientX, e.clientY);
        if (punto) { const sel = getSelection(); sel.removeAllRanges(); sel.addRange(punto); }
      }
      document.execCommand("insertHTML", false, pezzo);
      aggiorna();
    });

    // La casella resta nel modulo (nascosta) e viene inviata con il testo formattato.
    area.required = false;
    area.hidden = true;
    area.parentNode.insertBefore(contenitore, area);
    if (!bloccato) contenitore.appendChild(barra);
    contenitore.appendChild(editor);
    contenitore.appendChild(area);
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
    document.querySelectorAll("form textarea").forEach(preparaEditor);
    // Righe aggiunte nell'amministrazione (es. "Aggiungi un'altra misura")
    document.addEventListener("formset:added", function (e) {
      e.target.querySelectorAll("textarea").forEach(preparaEditor);
    });
    preparaNorme();
    preparaSezioni();
  });
})();
