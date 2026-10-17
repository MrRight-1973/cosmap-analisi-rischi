// Pagine della validazione (EN ISO 13849-2): prove di una funzione (modo "prove") e misure contro i guasti
// sistematici della revisione (modo "sistematiche"). Ricavate dal passo 6 della safety evaluation, con lo stesso
// validazione.js; i dati restano nella stessa forma JSON ({ esiti, extra, esecutore, data } e { esiti, swVersione, swFirma }).
(function () {
  'use strict';
  const V = window.Validazione;
  const DATI = JSON.parse(document.getElementById('dati-validazione').textContent);
  const MOD = DATI.modificabile;
  const PROVE = DATI.modo === 'prove';
  const app = document.getElementById('validazione');

  const X = PROVE
    ? Object.assign({ esiti: {}, extra: [], esecutore: '', data: '' }, DATI.prove)
    : Object.assign({ esiti: {}, swVersione: '', swFirma: '' }, DATI.sistematiche);
  // La funzione nella forma di validazione.js: schema a blocchi dal calcolo, prove in f.validazione
  const F = PROVE ? Object.assign({}, DATI.dettaglio, { nome: DATI.nome, validazione: X }) : null;
  if (F) F.sottosistemi = F.sottosistemi || [];
  const UI = { salvato: JSON.stringify(X), stato: '', errore: '' };
  const uid = () => Math.random().toString(36).slice(2, 9);

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'class') el.className = v;
      else if (k === 'value') el.value = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c.nodeType ? c : String(c));
    return el;
  }
  function campo(label, get, set, opt = {}) {
    const inp = h('input', { type: opt.type || 'text', value: get() || '', placeholder: opt.placeholder,
      onchange: e => { set(e.target.value.trim()); render(); } });
    return label ? h('label', {}, label, inp) : inp;
  }
  function selEsito(get, set) {
    return h('select', { class: 'esito', onchange: e => { set(e.target.value); render(); } },
      V.ESITI.map(([v, t]) => h('option', { value: v, selected: (get() || '') === v }, t)));
  }
  const voce = (esiti, k) => (esiti[k] = esiti[k] || {});
  function pill(r) {
    return r.completa ? h('span', { class: 'pill ok' }, 'validata')
      : r.ko ? h('span', { class: 'pill bad' }, `${r.ko} non OK`) : h('span', { class: 'pill mute' }, `${r.aperte} da eseguire`);
  }
  // Toglie le voci vuote prima del salvataggio
  function pulito() {
    const esiti = Object.fromEntries(Object.entries(X.esiti).filter(([, e]) => e && (e.esito || e.note)));
    return { ...X, esiti };
  }

  function vistaProve() {
    const lista = V.prove(F);
    return [
      h('div', { class: 'grid' },
        campo('Prove eseguite da', () => X.esecutore, v => { X.esecutore = v; }),
        campo('Data', () => X.data, v => { X.data = v; }, { type: 'date' })),
      h('div', { class: 'scroll', style: 'margin-top:10px' }, h('table', { class: 'val' },
        h('thead', {}, h('tr', {}, h('th', {}, 'N.'), h('th', {}, 'Prova'), h('th', {}, 'Risultato atteso'), h('th', {}, 'Esito'), h('th', {}, 'Note'), h('th', {}))),
        h('tbody', {}, lista.map((p, j) => h('tr', {},
          h('td', {}, j + 1),
          h('td', {}, p.extra ? campo(null, () => p.extra.testo, x => { p.extra.testo = x; }, { placeholder: 'Prova' }) : p.testo),
          h('td', {}, p.extra ? campo(null, () => p.extra.atteso, x => { p.extra.atteso = x; }, { placeholder: 'Risultato atteso' }) : p.atteso),
          h('td', {}, selEsito(() => p.esito, x => { voce(X.esiti, p.key).esito = x; })),
          h('td', {}, campo(null, () => p.note, x => { voce(X.esiti, p.key).note = x; })),
          h('td', {}, p.extra && MOD ? h('button', { type: 'button', title: 'Elimina la prova',
            onclick: () => { X.extra = X.extra.filter(x => x !== p.extra); delete X.esiti[p.key]; render(); } }, '×') : null)))))),
      MOD ? h('div', { class: 'row' }, h('button', { type: 'button', onclick: () => { X.extra.push({ id: uid(), testo: '', atteso: '' }); render(); } }, '+ prova')) : null,
    ];
  }

  function vistaSistematiche() {
    return [
      V.MISURE_SISTEMATICHE.map(g => [h('h3', { class: 'gruppo' }, g.gruppo), h('div', { class: 'scroll' }, h('table', { class: 'val' },
        h('thead', {}, h('tr', {}, h('th', {}, 'Misura'), h('th', {}, 'Esito'), h('th', {}, 'Note / riferimento'))),
        h('tbody', {}, g.misure.map(([id, testo]) => h('tr', {}, h('td', {}, testo),
          h('td', {}, selEsito(() => (X.esiti[id] || {}).esito, v => { voce(X.esiti, id).esito = v; })),
          h('td', {}, campo(null, () => (X.esiti[id] || {}).note, v => { voce(X.esiti, id).note = v; })))))))]),
      h('div', { class: 'grid' },
        campo('Progetto software / versione', () => X.swVersione, v => { X.swVersione = v; }),
        campo('Firma del programma F', () => X.swFirma, v => { X.swFirma = v; }, { placeholder: 'es. firma complessiva F' })),
    ];
  }

  const modificata = () => JSON.stringify(X) !== UI.salvato;
  async function salva() {
    UI.stato = 'salvataggio…'; UI.errore = ''; render();
    const corpo = PROVE ? { dati: pulito(), prove: V.proveAuto(F).map(p => ({ key: p.key })) } : { dati: pulito() };
    try {
      const risposta = await fetch(DATI.salva_url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': DATI.csrf },
        body: JSON.stringify(corpo),
      });
      const esito = await risposta.json();
      if (!risposta.ok) throw new Error(esito.errore || risposta.status);
      UI.salvato = JSON.stringify(X);
      UI.stato = esito.messaggio;
    } catch (e) {
      UI.stato = '';
      UI.errore = 'Non salvato: ' + e.message;
    }
    render();
  }
  window.addEventListener('beforeunload', e => { if (MOD && modificata()) { e.preventDefault(); e.returnValue = ''; } });

  // Un "change" scatta anche quando il clic su Salva toglie il fuoco al campo: si ridisegna una volta alla volta
  let disegno = false;
  function render() {
    if (disegno) { setTimeout(render); return; }
    disegno = true;
    try { disegna(); } finally { disegno = false; }
  }
  function disegna() {
    const y = window.scrollY;
    // Nelle prove la barra resta in alto; nelle misure sistematiche il salvataggio sta in fondo alla tabella
    const barra = h('div', { class: PROVE ? 'barra' : 'barra in-fondo' },
      PROVE ? h('span', {}, 'Prove: ', pill(V.riepilogo(V.prove(F)))) : null,
      h('span', { class: 'spacer' }),
      MOD ? h('button', { type: 'button', class: 'primario', disabled: !modificata(), onclick: salva },
        modificata() ? (PROVE ? 'Salva prove' : 'Salva misure') : 'Salvato') : null);
    const avviso = UI.errore ? h('p', { class: 'messaggio error' }, UI.errore) : UI.stato ? h('p', { class: 'messaggio success' }, UI.stato) : null;
    const contenuto = h('div', {}, PROVE ? vistaProve() : vistaSistematiche());
    app.replaceChildren(...(PROVE ? [barra, avviso, contenuto] : [contenuto, avviso, barra]).filter(Boolean));
    if (!MOD) app.querySelectorAll('input, select').forEach(el => { el.disabled = true; });
    window.scrollTo(0, y);
  }
  render();
})();
