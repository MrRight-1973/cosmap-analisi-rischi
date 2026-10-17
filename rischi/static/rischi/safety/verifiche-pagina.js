// Pagina delle verifiche elettriche di un quadro (IEC 60204-1, cap. 18): testata, prove con valore misurato ed
// esito, registro delle misure sul campo (collegamenti equipotenziali e cavi, incolla da Excel). Ricavata dal passo 6
// della safety evaluation con lo stesso validazione.js; i dati restano nella stessa forma JSON (S.elettriche).
(function () {
  'use strict';
  const V = window.Validazione;
  const DATI = JSON.parse(document.getElementById('dati-verifica').textContent);
  const MOD = DATI.modificabile;
  const app = document.getElementById('verifica');
  const el = Object.assign({ esiti: {}, extra: [], equipotenziali: [], cavi: [] }, DATI.dati);
  const X = { quadro: DATI.quadro };
  const UI = { salvato: JSON.stringify([X, el]), stato: '', errore: '', incolla: null };
  const uid = () => Math.random().toString(36).slice(2, 9);

  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (k === 'class') e.className = v;
      else if (k === 'value') e.value = v;
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) e.append(c.nodeType ? c : String(c));
    return e;
  }
  function campo(label, get, set, opt = {}) {
    const inp = h('input', { type: opt.type || 'text', value: get() || '', placeholder: opt.placeholder, style: opt.style,
      onchange: e => { set(e.target.value.trim()); render(); } });
    return label ? h('label', {}, label, inp) : inp;
  }
  function selEsito(get, set) {
    return h('select', { class: 'esito', onchange: e => { set(e.target.value); render(); } },
      V.ESITI.map(([v, t]) => h('option', { value: v, selected: (get() || '') === v }, t)));
  }
  function pill(r) {
    return r.completa ? h('span', { class: 'pill ok' }, 'tutte OK')
      : r.ko ? h('span', { class: 'pill bad' }, `${r.ko} non OK`) : h('span', { class: 'pill mute' }, `${r.aperte} senza esito`);
  }
  const voce = k => (el.esiti[k] = el.esiti[k] || {});
  // Valore delle righe 18.2.2, 18.2.3 e 18.3 ricavato dal registro misure, se il campo è vuoto
  function dalRegistro(key) {
    const r = V.riepilogoRegistro(el);
    const v = { continuita: r.rpeMax && `max ${r.rpeMax}`, anello: r.zsMax && `max ${r.zsMax}`, isolamento: r.isoMin && `min ${r.isoMin}` }[key];
    return v ? v + ' (registro)' : '';
  }

  function vistaProve() {
    const lista = V.proveElettriche(el);
    return h('div', {},
      h('div', { class: 'row testa' }, h('h3', {}, 'Prove'), h('span', { class: 'spacer' }), pill(V.riepilogo(lista))),
      h('p', { class: 'note' }, `Criteri riassunti da ${V.FONTE_ELETTRICHE}. Per più punti di misura (es. un circuito per riga) aggiungi una prova.`),
      h('div', { class: 'grid' },
        campo('Equipaggiamento / quadro', () => X.quadro, x => { X.quadro = x; }),
        campo('Tensione nominale di alimentazione', () => el.tensione, x => { el.tensione = x; }, { placeholder: 'es. 400 V 50 Hz TN-S' }),
        campo('Strumento (modello, matricola)', () => el.strumento, x => { el.strumento = x; }),
        campo('Scadenza taratura strumento', () => el.taratura, x => { el.taratura = x; }, { type: 'date' }),
        campo('Tensione di prova isolamento', () => el.vprova, x => { el.vprova = x; }, { placeholder: 'es. 500 V c.c.' }),
        campo('Prove eseguite da', () => el.esecutore, x => { el.esecutore = x; }),
        campo('Data', () => el.data, x => { el.data = x; }, { type: 'date' })),
      h('div', { class: 'scroll', style: 'margin-top:10px' }, h('table', { class: 'val' },
        h('thead', {}, h('tr', {}, ['Rif.', 'Prova', 'Criterio', 'Misurato', 'Esito', 'Note', ''].map(t => h('th', {}, t)))),
        h('tbody', {}, lista.map(p => h('tr', {},
          h('td', {}, p.clausola || ''),
          h('td', {}, p.extra ? campo(null, () => p.extra.testo, x => { p.extra.testo = x; }, { placeholder: 'Prova o punto di misura' }) : p.testo),
          h('td', {}, p.extra ? campo(null, () => p.extra.criterio, x => { p.extra.criterio = x; }, { placeholder: 'Criterio' }) : p.criterio),
          h('td', { style: 'white-space:nowrap' },
            campo(null, () => p.misurato, x => { voce(p.key).misurato = x; }, { placeholder: dalRegistro(p.key), style: 'width:130px' }), ' ',
            p.extra ? campo(null, () => p.extra.unita, x => { p.extra.unita = x; }, { placeholder: 'unità', style: 'width:56px' }) : p.unita),
          h('td', {}, selEsito(() => p.esito, x => { voce(p.key).esito = x; })),
          h('td', {}, campo(null, () => p.note, x => { voce(p.key).note = x; })),
          h('td', {}, p.extra && MOD ? h('button', { type: 'button', title: 'Elimina la prova',
            onclick: () => { el.extra = el.extra.filter(x => x !== p.extra); delete el.esiti[p.key]; render(); } }, '×') : null)))))),
      MOD ? h('div', { class: 'row' }, h('button', { type: 'button', onclick: () => { el.extra.push({ id: uid(), testo: '', criterio: '', unita: '' }); render(); } }, '+ prova')) : null);
  }

  // ---- registro misure sul campo ----
  const LARGHEZZE = { sigla: 70, percorso: 90, tipo: 84, formazione: 76, protezione: 70, sezione: 48, in: 44, note: 110, punto: 180, conduttore: 100 };
  function cella(riga, k) {
    const m = V.MISURE_CAVI.includes(k) || k === 'rpe' ? V.leggiMisura(riga[k]) : null;
    const iso = V.ISO.some(([c]) => c === k);
    const ko = iso && m && (isNaN(m.v) || m.op === '<' || m.v < V.ISO_MIN);
    return h('input', { value: riga[k] || '', class: (m && isNaN(m.v) ? 'invalido' : '') + (ko ? ' ko' : ''), style: `width:${LARGHEZZE[k] || 52}px`,
      title: ko ? `Isolamento sotto ${V.ISO_MIN} MΩ` : m && isNaN(m.v) ? 'Valore non numerico (ammessi anche > e <, es. >1)' : '',
      onchange: e => { riga[k] = e.target.value.trim(); render(); } });
  }
  function tabellaRegistro(chiave, colonne) {
    const righe = el[chiave];
    return [
      h('div', { class: 'scroll' }, h('table', { class: 'val reg' },
        h('thead', {}, h('tr', {}, h('th', {}, 'N.'), colonne.map(([, t]) => h('th', {}, t)), chiave === 'cavi' ? h('th', {}, 'Isol.') : null, h('th', {}))),
        h('tbody', {}, righe.map((r, i) => h('tr', {},
          h('td', {}, i + 1),
          colonne.map(([k]) => h('td', {}, cella(r, k))),
          chiave === 'cavi' ? h('td', { class: { ok: 'ok', ko: 'bad' }[V.esitoIsolamento(r)] || 'mute' }, { ok: 'OK', ko: 'Non OK' }[V.esitoIsolamento(r)] || '—') : null,
          h('td', { style: 'white-space:nowrap' }, MOD ? [
            h('button', { type: 'button', title: 'Duplica la riga (senza i valori misurati)', onclick: () => {
              const c = { ...r, id: uid() }; V.MISURE_CAVI.concat('rpe', 'note').forEach(k => { delete c[k]; }); righe.splice(i + 1, 0, c); render(); } }, '⧉'), ' ',
            h('button', { type: 'button', title: 'Elimina la riga', onclick: () => { righe.splice(i, 1); render(); } }, '×')] : null)))))),
      MOD ? h('div', { class: 'row' },
        h('button', { type: 'button', onclick: () => { righe.push({ id: uid() }); render(); } }, chiave === 'cavi' ? '+ cavo' : '+ collegamento'),
        h('button', { type: 'button', onclick: () => { UI.incolla = UI.incolla === chiave ? null : chiave; render(); } }, 'Incolla da Excel / Calc'),
        righe.length ? h('button', { type: 'button', onclick: () => { if (confirm(`Svuotare la tabella (${righe.length} righe)?`)) { el[chiave] = []; render(); } } }, 'Svuota') : null) : null,
      UI.incolla === chiave ? h('div', { style: 'margin-top:8px' },
        h('p', { class: 'note', style: 'margin:0 0 4px' }, `Copia le righe dal foglio di calcolo e incollale qui, con le colonne in questo ordine: ${colonne.map(c => c[1]).join(' · ')}. Le righe si aggiungono a quelle già presenti.`),
        h('textarea', { id: 'incolla', rows: 6, style: 'width:100%', placeholder: 'incolla qui…' }),
        h('div', { class: 'row' }, h('button', { type: 'button', class: 'primario', onclick: () => {
          const nuove = V.daTesto(document.getElementById('incolla').value, colonne).map(r => ({ id: uid(), ...r }));
          righe.push(...nuove); UI.incolla = null; render(); } }, 'Aggiungi le righe'))) : null,
    ];
  }
  function vistaRegistro() {
    const r = V.riepilogoRegistro(el);
    return h('div', { style: 'margin-top:22px' },
      h('div', { class: 'row testa' }, h('h3', {}, 'Registro misure sul campo'), h('span', { class: 'spacer' }),
        r.isoKo.length ? h('span', { class: 'pill bad' }, `isolamento non OK: ${r.isoKo.join(', ')}`) : null,
        r.senzaMisure ? h('span', { class: 'pill mute' }, `${r.senzaMisure} righe da misurare`) : null),
      h('p', { class: 'note' }, 'Elenca i collegamenti di protezione e i cavi, salva e stampa il modulo per i tecnici (usa i dati salvati), poi riporta qui i valori misurati. Si accettano anche valori come >1 o <0,1. I valori peggiori compaiono nelle righe 18.2.2, 18.2.3 e 18.3 se lì non scrivi niente.'),
      h('h4', {}, 'Collegamenti equipotenziali (18.2.2)'),
      tabellaRegistro('equipotenziali', V.COLONNE_EQUI),
      h('h4', {}, 'Cavi: continuità PE (18.2.2), anello di guasto (18.2.3), isolamento [MΩ] (18.3)'),
      tabellaRegistro('cavi', V.COLONNE_CAVI));
  }

  const modificata = () => JSON.stringify([X, el]) !== UI.salvato;
  async function salva() {
    UI.stato = 'salvataggio…'; UI.errore = ''; render();
    const prove = V.proveElettriche(el);
    const registro = V.riepilogoRegistro(el);
    try {
      const risposta = await fetch(DATI.salva_url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': DATI.csrf },
        body: JSON.stringify({ quadro: X.quadro, dati: el, risultato: { riepilogo: V.riepilogo(prove), registro } }),
      });
      const esito = await risposta.json();
      if (!risposta.ok) throw new Error(esito.errore || risposta.status);
      UI.salvato = JSON.stringify([X, el]);
      UI.stato = esito.messaggio;
    } catch (e) {
      UI.stato = '';
      UI.errore = 'Non salvato: ' + e.message;
    }
    render();
  }
  window.addEventListener('beforeunload', e => { if (MOD && modificata()) { e.preventDefault(); e.returnValue = ''; } });

  // Un "change" scatta anche quando il clic su un pulsante toglie il fuoco al campo: si ridisegna una volta alla volta
  let disegno = false;
  function render() {
    if (disegno) { setTimeout(render); return; }
    disegno = true;
    try { disegna(); } finally { disegno = false; }
  }
  function disegna() {
    const y = window.scrollY;
    const barra = h('div', { class: 'barra' },
      h('span', {}, 'Prove: ', pill(V.riepilogo(V.proveElettriche(el)))),
      h('span', { class: 'spacer' }),
      MOD ? h('button', { type: 'button', class: 'primario', disabled: !modificata(), onclick: salva }, modificata() ? 'Salva verifica' : 'Salvata') : null);
    const avviso = UI.errore ? h('p', { class: 'messaggio error' }, UI.errore) : UI.stato ? h('p', { class: 'messaggio success' }, UI.stato) : null;
    app.replaceChildren(...[barra, avviso, vistaProve(), vistaRegistro()].filter(Boolean));
    if (!MOD) app.querySelectorAll('input, select, textarea').forEach(e => { e.disabled = true; });
    window.scrollTo(0, y);
  }
  render();
})();
