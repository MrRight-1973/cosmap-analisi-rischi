// Pagina "Calcolo PL" della funzione di sicurezza: schema a blocchi, componenti dall'archivio, calcolo dei
// sottosistemi e verifica PL ≥ PLr. Ricavata dai passi 2-5 della safety evaluation, con lo stesso engine.js
// e schema.js; il dettaglio resta nella stessa forma JSON, così le valutazioni esistenti si importano senza conversioni.
(function () {
  'use strict';
  const E = window.SafetyEngine;
  const Sc = window.Schema;
  const DATI = JSON.parse(document.getElementById('dati-valutazione').textContent);
  const MOD = DATI.modificabile;
  const app = document.getElementById('valutazione');

  // La funzione nella forma di engine.js: nome, S/F/P dalla funzione della revisione, il resto dal dettaglio salvato
  const F = Object.assign({ sottosistemi: [] }, DATI.dettaglio, { nome: DATI.nome, S: DATI.S, F: DATI.F, P: DATI.P });
  F.sottosistemi = F.sottosistemi || [];
  const MT = F.missionTime || 20;
  let A = [];
  const UI = { tab: 'schema', sel: null, salvato: JSON.stringify(F), stato: '', errore: '', soloUtilizzati: false };
  try { UI.soloUtilizzati = localStorage.getItem('safety-eval-solo-utilizzati') === '1'; } catch (e) { /* niente */ }

  const uid = () => Math.random().toString(36).slice(2, 9);
  // Numeri all'italiana: virgola decimale, punti delle migliaia, anche notazione E. Vuoto → null, non numerico → NaN.
  function num(v) {
    let s = String(v ?? '').trim().replace(/\s+/g, '');
    if (!s) return null;
    if (s.includes(',')) s = s.replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.');
    else if (/^\d{1,3}(\.\d{3}){2,}$/.test(s)) s = s.replace(/\./g, '');
    return /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(s) ? Number(s) : NaN;
  }
  const numTxt = v => (v == null || v === '' ? '' : String(v).replace('.', ','));
  const fmt = (n, d = 2) => (n == null || isNaN(n) ? '—' : n.toLocaleString('it-IT', { maximumFractionDigits: d }));

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
      else if (k === 'class') el.className = v;
      else if (k === 'value') el.value = v;
      else if (k === 'checked') el.checked = !!v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const c of kids.flat(Infinity)) if (c != null && c !== false) el.append(c.nodeType ? c : String(c));
    return el;
  }
  function field(label, get, set, opt = {}) {
    let inp;
    if (opt.options) {
      inp = h('select', { onchange: e => { set(e.target.value || null); render(); } },
        opt.options.map(([v, t]) => h('option', { value: v ?? '', selected: (get() ?? '') === (v ?? '') }, t)));
    } else if (opt.type === 'number') {
      // campo di testo: type=number scarta la virgola decimale
      inp = h('input', { type: 'text', inputmode: 'decimal', value: numTxt(get()), placeholder: opt.placeholder,
        onchange: e => {
          let v = num(e.target.value);
          if (Number.isNaN(v) || (v != null && opt.min != null && v < opt.min)) {
            e.target.classList.add('invalido');
            e.target.title = Number.isNaN(v) ? 'Numero non valido: usa la virgola per i decimali, es. 4,29' : `Valore minimo ${opt.min}`;
            return;
          }
          if (opt.pfh && v > 0 && v < 1e-3) v = Math.round(v * 1e9 * 1e6) / 1e6; // PFH scritto in 1/h
          set(v); render();
        } });
    } else {
      inp = h('input', { type: 'text', value: get() ?? '', placeholder: opt.placeholder, onchange: e => { set(e.target.value); render(); } });
    }
    return label ? h('label', {}, label, inp) : inp;
  }
  function check(label, get, set) {
    return h('label', { class: 'chk' }, h('input', { type: 'checkbox', checked: get(), onchange: e => { set(e.target.checked); render(); } }), label);
  }
  const plPill = (pl, req) => {
    if (!pl) return h('span', { class: 'pill mute' }, 'n.d.');
    const cls = req ? (E.plAtLeast(pl, req) ? 'ok' : 'bad') : '';
    return h('span', { class: 'pill ' + cls }, 'PL ' + pl);
  };
  const art = id => A.find(a => a.id === id);
  const valuta = () => E.evalFunction(F, A, MT);
  function issues(errors, warns) {
    if (!errors.length && !warns.length) return null;
    return h('ul', { class: 'list' }, errors.map(e => h('li', { class: 'bad' }, e)), warns.map(w => h('li', { class: 'warn' }, w)));
  }

  // ---- schema a blocchi ----
  const RUOLI = [['rilevamento', 'Rilevamento (sensori, pulsanti)'], ['logica', 'Logica (F-CPU, relè di sicurezza)'], ['attuazione', 'Attuazione (azionamenti, contattori)'], ['comunicazione', 'Comunicazione']];
  const METODI = [['pfh', 'PFH da certificato del costruttore'], ['arch', 'Architettura designata (MTTFd, DC, CCF)']];
  const nuovoSS = (ruolo, percorso) => ({ id: uid(), nome: RUOLI.find(r => r[0] === ruolo)[1].split(' (')[0], ruolo, percorso, metodo: ruolo === 'rilevamento' ? 'arch' : 'pfh', categoria: null, componenti: [], ccf: {}, pfhK1: null });
  function schema(editable) {
    const r = valuta();
    const res = new Map(r.subs.map(x => [x.ss, x.r]));
    const nomi = Sc.percorsi(F);
    const multi = nomi.length > 1;
    const blocco = ss => {
      const x = res.get(ss);
      const n = ss.componenti.length;
      const comune = multi && !(ss.percorso || '').trim();
      return h(editable ? 'button' : 'div', { type: 'button', class: `blk r-${ss.ruolo}${comune ? ' comune' : ''}${UI.sel === ss.id ? ' sel' : ''}`,
        onclick: editable ? () => { UI.sel = UI.sel === ss.id ? null : ss.id; render(); } : null },
        h('span', { class: 'ruolo' }, ss.ruolo + (comune ? ' · comune' : '')),
        h('b', {}, ss.nome || '—'),
        h('div', { class: 'mute' }, ss.metodo === 'arch' ? `cat. ${ss.categoria || '?'} · MTTFd/DC` : 'PFH da certificato'),
        h('div', {}, n ? `${n} articol${n === 1 ? 'o' : 'i'}` : h('span', { class: 'warn' }, 'nessun articolo')),
        n && x ? h('div', {}, x.nano != null ? `${fmt(x.nano)}·10⁻⁹/h ` : '', plPill(x.pl)) : null);
    };
    const infoCorsia = nome => {
      const path = r.paths.find(p => p.nome === (nome || 'unico'));
      const proprio = F.sottosistemi.some(ss => (ss.percorso || '').trim() === nome);
      const peggiore = multi && r.worst && r.worst.pl && r.worst.complete && path && r.worst === path;
      return { path, proprio, peggiore };
    };
    const nomeCorsia = (nome, peggiore) => h('div', { class: 'lane-name' + (peggiore ? ' peggiore' : '') },
      !multi ? 'Percorso unico'
        : editable ? h('input', { value: nome, title: 'Nome del percorso', onchange: e => { if (!Sc.rinominaPercorso(F, nome, e.target.value)) e.target.value = nome; render(); } })
        : nome,
      peggiore ? h('span', { class: 'piccolo' }, 'percorso peggiore') : null,
      editable && multi ? h('a', { href: '#', class: 'piccolo', onclick: e => { e.preventDefault();
        if (confirm(`Eliminare il percorso "${nome}" e i blocchi solo suoi?`)) { Sc.eliminaPercorso(F, nome); render(); } } }, 'elimina') : null);
    const aggiungi = (nome, comune) => editable ? h('select', { class: 'lane-add', onchange: e => { const ss = nuovoSS(e.target.value, comune ? '' : nome); F.sottosistemi.push(ss); UI.sel = ss.id; render(); } },
      h('option', { value: '', selected: true, disabled: true }, comune ? '+ blocco comune' : '+ blocco'), RUOLI.map(([k, t]) => h('option', { value: k }, t.split(' (')[0]))) : null;
    const risultato = ({ path, proprio }) => h('div', { class: 'lane-res' },
      multi && !proprio ? h('span', { class: 'warn' }, 'manca l\'iniziatore')
        : path ? [h('span', {}, `Σ PFH ${fmt(path.nano)}·10⁻⁹/h`), path.complete ? plPill(path.pl, r.plr) : h('span', { class: 'warn' }, 'incompleto')] : null);
    const serie = blocchi => blocchi.flatMap((ss, i) => [i ? h('span', { class: 'arrow' }, '→') : null, blocco(ss)]);
    const corsia = nome => {
      const info = infoCorsia(nome);
      return h('div', { class: 'lane' }, nomeCorsia(nome, info.peggiore), serie(Sc.catena(F, nome)), aggiungi(nome), risultato(info));
    };
    const conf = Sc.confluenza(F);
    const confluenti = () => h('div', { class: 'schema conf' }, nomi.flatMap((nome, k) => {
      const info = infoCorsia(nome);
      const pos = k === 0 ? 'primo' : k === nomi.length - 1 ? 'ultimo' : 'mezzo';
      const propri = conf.propri.get(nome);
      return [
        h('div', { class: 'nome-add' }, nomeCorsia(nome, info.peggiore), aggiungi(nome)),
        h('div', { class: 'propri' }, propri.length ? serie(propri) : h('span', { class: 'warn', style: 'align-self:center' }, 'nessun blocco proprio'), h('span', { class: 'coda' })),
        h('div', { class: 'bus ' + pos }, k === 0 ? h('span', { class: 'punta' }, '▶') : null),
        k === 0 ? h('div', { class: 'comuni', style: `grid-row: span ${nomi.length}` }, h('div', { class: 'catena' }, serie(conf.comuni)), aggiungi(nome, true)) : null,
        risultato(info),
      ];
    }));
    return h('div', {},
      h('div', { class: 'legenda' }, RUOLI.map(([k, t]) => h('span', { class: 'r-' + k }, t.split(' (')[0])),
        multi ? h('span', { class: 'leg-comune' }, conf ? 'tratteggiato = comune: i percorsi confluiscono qui' : 'tratteggiato = comune a tutti i percorsi') : null),
      h('div', { class: 'scroll' }, conf ? confluenti() : h('div', { class: 'schema' }, nomi.map(corsia))),
      h('p', { class: 'note' }, multi
        ? `La funzione ha il PL del percorso peggiore: ${r.worst && r.worst.pl ? 'PL ' + r.worst.pl + ' (' + r.worst.nome + ')' : 'non ancora calcolabile'}${r.plr ? ', richiesto PL ' + r.plr : ''}.`
        : 'Tutti i blocchi sono in serie: devono funzionare tutti perché la funzione intervenga.'));
  }
  function editorBlocco() {
    const i = F.sottosistemi.findIndex(x => x.id === UI.sel);
    if (i < 0) return h('p', { class: 'note' }, F.sottosistemi.length ? 'Clicca un blocco per modificarlo.' : 'Aggiungi i blocchi con "+ blocco": rilevamento, logica e attuazione.');
    const ss = F.sottosistemi[i];
    const nomi = Sc.percorsi(F).filter(Boolean);
    return h('section', { class: 'r-' + ss.ruolo + ' bordo-ruolo' },
      h('div', { class: 'grid' },
        field('Nome blocco', () => ss.nome, v => ss.nome = v),
        field('Ruolo', () => ss.ruolo, v => ss.ruolo = v, { options: RUOLI }),
        nomi.length ? field('Percorso', () => ss.percorso || null, v => ss.percorso = v || '', { options: [[null, 'Comune a tutti i percorsi'], ...nomi.map(n => [n, n])] }) : null,
        field('Metodo', () => ss.metodo, v => ss.metodo = v, { options: METODI }),
        ss.metodo === 'arch' ? field('Categoria', () => ss.categoria, v => ss.categoria = v, { options: [[null, '—'], ['B', 'B'], ['1', '1'], ['2', '2'], ['3', '3'], ['4', '4']] }) : null),
      ss.metodo === 'arch' && ss.categoria === '1' ? check('Componenti ben collaudati (ISO 13849-2)', () => ss.collaudati, v => ss.collaudati = v) : null,
      h('div', { class: 'row' },
        h('button', { type: 'button', onclick: () => { UI.tab = 'componenti'; render(); } }, 'Scegli gli articoli →'),
        h('span', { class: 'spacer' }),
        h('button', { type: 'button', onclick: () => { F.sottosistemi.splice(i, 1); UI.sel = null; render(); } }, 'Elimina blocco')));
  }
  function vistaSchema() {
    return [
      h('p', { class: 'sub' }, 'In ogni riga i blocchi sono in serie, da chi rileva a chi arresta. Se la funzione può partire da iniziatori diversi, aggiungi un percorso alternativo per ciascuno: la funzione ha il PL del percorso peggiore. I blocchi comuni (F-CPU, azionamenti) stanno in tutti i percorsi.'),
      h('section', {}, schema(MOD),
        MOD ? h('div', { class: 'row' }, h('button', { type: 'button', onclick: () => { Sc.aggiungiPercorso(F); render(); } }, '+ Percorso alternativo')) : null),
      MOD ? editorBlocco() : null,
    ];
  }

  // ---- componenti ----
  const TIPO_RUOLO = { rilevamento: 'sensore', logica: 'logica', attuazione: 'attuatore', comunicazione: 'comunicazione' };
  const SEL = {};
  function candidati(ss) {
    const s = SEL[ss.id] || {};
    const tipo = s.tutti ? '' : TIPO_RUOLO[ss.ruolo];
    const q = (s.testo || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    return A.filter(a => (!tipo || a.tipo === tipo) && (!UI.soloUtilizzati || a.utilizzato) &&
      q.every(t => `${a.codice} ${a.descrizione} ${a.produttore}`.toLowerCase().includes(t)));
  }
  function sceltaArticolo(c, ss) {
    const gruppi = new Map();
    const lista = candidati(ss);
    const scelto = art(c.articoloId);
    if (scelto && !lista.includes(scelto)) lista.push(scelto);
    for (const a of lista.sort((x, y) => `${x.produttore}${x.codice}`.localeCompare(`${y.produttore}${y.codice}`))) {
      const k = a.produttore || '(senza produttore)';
      if (!gruppi.has(k)) gruppi.set(k, []);
      gruppi.get(k).push(a);
    }
    return h('select', { onchange: e => { c.articoloId = e.target.value || null; render(); } },
      h('option', { value: '' }, '— scegli —'),
      [...gruppi].map(([g, elenco]) => h('optgroup', { label: g }, elenco.map(a =>
        h('option', { value: a.id, selected: a.id === c.articoloId }, `${a.codice} · ${a.descrizione || ''}${a.verificato ? '' : ' (da verificare)'}`)))));
  }
  function filtro(ss) {
    const s = SEL[ss.id] ||= { testo: '', tutti: false };
    const tipo = TIPO_RUOLO[ss.ruolo];
    return h('div', { class: 'row filtro' },
      h('input', { type: 'search', 'data-ss': ss.id, value: s.testo, placeholder: 'cerca codice, descrizione, costruttore',
        oninput: e => { s.testo = e.target.value; clearTimeout(s.t); s.t = setTimeout(() => { render(); const i = app.querySelector(`input[data-ss="${ss.id}"]`); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } }, 250); } }),
      h('label', { class: 'chk' }, h('input', { type: 'checkbox', checked: s.tutti, onchange: e => { s.tutti = e.target.checked; render(); } }), 'tutte le tipologie'),
      h('span', { class: 'mute' }, `${candidati(ss).length} articoli${UI.soloUtilizzati ? ' già utilizzati' : ''}${s.tutti || !tipo ? '' : ` di tipo "${tipo}"`}`));
  }
  function vistaComponenti() {
    return [
      h('p', { class: 'sub' }, 'Per ogni sottosistema scegli gli articoli dagli "Articoli di sicurezza" della libreria. Se un articolo manca, aggiungilo in libreria con la sua fonte.'),
      MOD ? check(`Scegli solo tra gli articoli già utilizzati (${A.filter(a => a.utilizzato).length} in libreria)`, () => UI.soloUtilizzati, v => {
        UI.soloUtilizzati = v; try { localStorage.setItem('safety-eval-solo-utilizzati', v ? '1' : '0'); } catch (e) { /* niente */ } }) : null,
      F.sottosistemi.length ? null : h('p', { class: 'warn' }, 'Prima costruisci lo schema a blocchi.'),
      Sc.gruppi(F).map(g => [
        g.titolo ? h('h3', { class: 'gruppo' }, g.comune ? g.titolo : `Percorso ${g.titolo}`,
          h('span', { class: 'mute' }, g.comune ? ' · in serie dopo ogni percorso' : ' · blocchi propri, in serie')) : null,
        g.blocchi.map(ss => {
          const arch = ss.metodo === 'arch';
          return h('section', { class: 'r-' + ss.ruolo + ' bordo-ruolo' },
            h('h3', {}, ss.nome, h('span', { class: 'mute' }, ` · ${ss.ruolo} · ${arch ? 'architettura designata, cat. ' + (ss.categoria || '?') : 'PFH da certificato'}`)),
            MOD ? filtro(ss) : null,
            h('div', { class: 'scroll' }, h('table', {},
              h('thead', {}, h('tr', {}, h('th', {}, 'Articolo'), h('th', {}, 'Qtà'),
                arch ? [h('th', {}, 'Canale'), h('th', {}, 'DC %'), h('th', {}, 'Giorni/anno'), h('th', {}, 'Ore/giorno'), h('th', {}, 'Ciclo [s]')] : h('th', {}, 'PFH cad.'),
                h('th', {}, 'Fonte'), h('th', {}))),
              h('tbody', {}, ss.componenti.map((c, i) => {
                const a = art(c.articoloId);
                const b10 = a && a.mttfd == null && a.b10d != null;
                return h('tr', {},
                  h('td', { class: 'col-articolo' }, MOD ? sceltaArticolo(c, ss) : a ? `${a.produttore} ${a.codice} · ${a.descrizione || ''}` : h('span', { class: 'warn' }, 'articolo non trovato')),
                  h('td', {}, field(null, () => c.qty, v => c.qty = v ?? 1, { type: 'number', min: 1 })),
                  arch ? [
                    h('td', {}, field(null, () => String(c.canale || 1), v => c.canale = Number(v), { options: [['1', '1'], ['2', '2']] })),
                    h('td', {}, field(null, () => c.dc, v => c.dc = v, { type: 'number', min: 0 })),
                    ...['dop', 'hop', 'tcycle'].map(k => h('td', {}, b10 ? field(null, () => c[k], v => c[k] = v, { type: 'number', min: 0 }) : h('span', { class: 'mute' }, '—'))),
                  ] : h('td', {}, a ? (a.pfh == null ? h('span', { class: 'warn' }, 'mancante') : fmt(a.pfh) + '·10⁻⁹/h') : '—'),
                  h('td', { class: 'col-fonte mute' }, a ? (a.fonte || h('span', { class: 'warn' }, 'senza fonte')) : ''),
                  h('td', {}, MOD ? h('button', { type: 'button', onclick: () => { ss.componenti.splice(i, 1); render(); } }, '×') : null));
              })))),
            MOD ? h('div', { class: 'row' }, h('button', { type: 'button', onclick: () => { ss.componenti.push({ articoloId: null, qty: 1, canale: 1, dc: null }); render(); } }, 'Aggiungi componente')) : null,
            arch ? h('p', { class: 'note' }, 'Giorni/anno, ore/giorno e tempo ciclo servono solo per gli articoli con B10d: MTTFd = B10d / (0,1 · nop), nop = giorni · ore · 3600 / ciclo (ISO 13849-1, allegato C).') : null);
        })]),
    ];
  }

  // ---- calcolo dei sottosistemi ----
  function vistaCalcolo() {
    const r = valuta();
    return [
      h('p', { class: 'sub' }, 'PFH in 10⁻⁹/h. Per l\'architettura designata compila le misure contro i guasti di causa comune: il PFH viene letto dalla tabella K.1 e si può sovrascrivere a mano.'),
      Sc.gruppi(F).flatMap(g => g.blocchi).map(ss => r.subs.find(x => x.ss === ss)).map(({ ss, r: x }) => h('section', {},
        h('div', { class: 'row testa' }, h('h3', {}, ss.nome), h('span', { class: 'spacer' }), plPill(x.pl)),
        x.metodo === 'pfh'
          ? h('div', { class: 'kv' }, h('span', {}, 'PFH somma'), h('span', {}, fmt(x.nano) + '·10⁻⁹/h'))
          : [
            h('div', { class: 'kv' },
              h('span', {}, 'MTTFd canale 1'), h('span', {}, fmt(x.ch1, 1) + ' anni'),
              h('span', {}, 'MTTFd canale 2'), h('span', {}, fmt(x.ch2, 1) + ' anni'),
              h('span', {}, 'MTTFd del sottosistema'), h('span', {}, `${fmt(x.mttfd, 1)} anni (${x.mttfdLevel || '—'})`),
              h('span', {}, 'DCavg'), h('span', {}, `${fmt(x.dcavg, 1)} % (${x.dcLevel || '—'})`),
              h('span', {}, 'Categoria'), h('span', {}, ss.categoria || '—')),
            E.CATEGORIE[ss.categoria] && E.CATEGORIE[ss.categoria].ccf ? [
              h('h4', {}, `Guasti di causa comune: ${x.ccf} / 100 punti (minimo ${E.CCF_MIN})`),
              E.CCF_MEASURES.map(m => check(`${m.testo} (${m.punti})`, () => !!(ss.ccf || {})[m.id], v => { ss.ccf = ss.ccf || {}; ss.ccf[m.id] = v; })),
            ] : null,
            h('div', { class: 'grid' },
              h('div', {},
                h('div', { class: 'kv' }, h('span', {}, 'PFH da tab. K.1'),
                  h('span', {}, x.k1 ? `${fmt(x.k1.nano, 3)}·10⁻⁹/h (cat. ${ss.categoria}, riga MTTFd ${fmt(x.k1.riga, 1)} anni)` : 'non ricavabile')),
                x.k1 ? h('p', { class: 'note' }, x.k1.fonte) : null),
              field('PFH inserito a mano [10⁻⁹/h], vuoto = tab. K.1', () => ss.pfhK1, v => ss.pfhK1 = v, { type: 'number', min: 0, pfh: true, placeholder: x.k1 ? fmt(x.k1.nano, 3) + ' dalla tab. K.1' : 'es. 42,9 oppure 4,29E-08 (1/h)' })),
          ],
        issues(x.errors, x.warns))),
    ];
  }

  // ---- verifica ----
  function vistaVerifica() {
    const r = valuta();
    return [
      h('p', { class: 'sub' }, 'Il PL della funzione è il minimo tra quello ricavato dalla somma dei PFH e quelli dei singoli sottosistemi (ISO 13849-1, 6.3).'),
      h('section', {},
        h('div', { class: 'row testa' }, h('span', {}, 'PLr ', h('b', {}, r.plr || '—')), h('span', { class: 'spacer' }), plPill(r.pl, r.plr)),
        h('p', { class: 'grande ' + (r.ok ? 'ok' : 'bad') }, r.ok ? 'Requisito soddisfatto' : 'Requisito non dimostrato'),
        h('div', { class: 'scroll' }, h('table', {},
          h('thead', {}, h('tr', {}, h('th', {}, 'Percorso'), h('th', {}, 'Sottosistemi in serie'), h('th', {}, 'PFH [10⁻⁹/h]'), h('th', {}, 'PL'))),
          h('tbody', {}, r.paths.map(p => h('tr', {}, h('td', {}, p.nome), h('td', {}, p.sottosistemi.join(' + ')),
            h('td', {}, fmt(p.nano) + (p.complete ? '' : ' (incompleto)')), h('td', {}, p.pl || 'n.d.')))))),
        issues(r.errors, r.warns)),
    ];
  }

  // ---- salvataggio ----
  const modificata = () => JSON.stringify(F) !== UI.salvato;
  async function salva() {
    UI.stato = 'salvataggio…'; UI.errore = ''; render();
    const { nome, S, F: f, P, ...dettaglio } = F;
    const r = valuta();
    try {
      const risposta = await fetch(DATI.salva_url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': DATI.csrf },
        body: JSON.stringify({ dettaglio, risultato: { pl: r.pl, pfh: r.worst && r.worst.complete ? r.worst.nano : null, ok: r.ok } }),
      });
      const esito = await risposta.json();
      if (!risposta.ok) throw new Error(esito.errore || risposta.status);
      UI.salvato = JSON.stringify(F);
      UI.stato = esito.messaggio;
    } catch (e) {
      UI.stato = '';
      UI.errore = 'Valutazione non salvata: ' + e.message;
    }
    render();
  }
  window.addEventListener('beforeunload', e => { if (MOD && modificata()) { e.preventDefault(); e.returnValue = ''; } });

  const SCHEDE = [['schema', 'Schema a blocchi'], ['componenti', 'Componenti'], ['calcolo', 'Calcolo'], ['verifica', 'Verifica PL ≥ PLr']];
  const VISTE = { schema: vistaSchema, componenti: vistaComponenti, calcolo: vistaCalcolo, verifica: vistaVerifica };
  let disegno = false;
  function render() {
    if (disegno) { setTimeout(render); return; }
    disegno = true;
    try {
      const r = valuta();
      const barra = h('div', { class: 'barra' },
        h('div', { class: 'schede' }, SCHEDE.map(([k, t]) => h('button', { type: 'button', class: 'scheda' + (UI.tab === k ? ' on' : ''), onclick: () => { UI.tab = k; render(); } }, t))),
        h('span', { class: 'spacer' }),
        h('span', {}, 'PLr ', h('b', {}, r.plr || '—'), ' · ', plPill(r.pl, r.plr)),
        MOD ? h('button', { type: 'button', class: 'primario', disabled: !modificata(), onclick: salva }, modificata() ? 'Salva valutazione' : 'Salvata') : null);
      const y = window.scrollY;
      const avviso = UI.errore ? h('p', { class: 'messaggio error' }, UI.errore) : UI.stato ? h('p', { class: 'messaggio success' }, UI.stato) : null;
      app.replaceChildren(...[barra, avviso, h('div', {}, VISTE[UI.tab]())].filter(Boolean));
      if (!MOD) app.querySelectorAll('input, select').forEach(el => { el.disabled = true; });
      window.scrollTo(0, y);
    } finally { disegno = false; }
  }

  app.replaceChildren(h('p', { class: 'note' }, 'Carico gli articoli di sicurezza…'));
  fetch(DATI.articoli_url, { cache: 'no-store' })
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(d => { A = d.articoli; render(); })
    .catch(e => { UI.errore = 'Articoli di sicurezza non caricati: ' + e.message; render(); });
})();
