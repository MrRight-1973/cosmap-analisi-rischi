// Motore di calcolo della safety evaluation (ISO 13849-1). Nessuna dipendenza:
// nel browser espone window.SafetyEngine, in Node module.exports.
// Unità: PFH in 10⁻⁹/h nei dati, conversione a 1/h solo per le soglie. MTTFd e T10d in anni.
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.SafetyEngine = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ISO 13849-1, tab. 2: PFH [1/h] per PL, limite superiore escluso. SIL secondo IEC 62061.
  const PL_LIMITS = [
    { pl: 'e', max: 1e-7, sil: 3 },
    { pl: 'd', max: 1e-6, sil: 2 },
    { pl: 'c', max: 3e-6, sil: 1 },
    { pl: 'b', max: 1e-5, sil: 1 },
    { pl: 'a', max: 1e-4, sil: 0 },
  ];
  const NONE = { pl: 'nessuno', max: Infinity, sil: 0 };
  const PL_RANK = { nessuno: 0, a: 1, b: 2, c: 3, d: 4, e: 5 };

  function toPL(pfh) {
    for (const l of PL_LIMITS) if (pfh < l.max) return l;
    return NONE;
  }
  function plMin(a, b) {
    if (a == null) return b;
    if (b == null) return a;
    return PL_RANK[a] <= PL_RANK[b] ? a : b;
  }
  function plAtLeast(pl, req) { return PL_RANK[pl] >= PL_RANK[req]; }

  // ISO 13849-1, allegato A, fig. A.1: grafo del rischio.
  function plr(S, F, P) {
    if (!S || !F || !P) return null;
    const i = (S === 'S2' ? 4 : 0) + (F === 'F2' ? 2 : 0) + (P === 'P2' ? 1 : 0);
    return ['a', 'b', 'b', 'c', 'c', 'd', 'd', 'e'][i];
  }

  // ISO 13849-1, allegato C (C.4): componenti con usura.
  function nop(dop, hop, tcycleS) { return (dop * hop * 3600) / tcycleS; }
  function b10dToMttfd(b10d, nopYear) { return b10d / (0.1 * nopYear); }
  function t10d(b10d, nopYear) { return b10d / nopYear; }

  // ISO 13849-1, tab. 5 (MTTFd per canale) e tab. 6 (DC).
  function mttfdLevel(y) {
    if (!(y >= 3)) return 'insufficiente';
    if (y < 10) return 'basso';
    if (y < 30) return 'medio';
    return 'alto';
  }
  function dcLevel(dc) {
    if (!(dc >= 60)) return 'nessuno';
    if (dc < 90) return 'basso';
    if (dc < 99) return 'medio';
    return 'alto';
  }
  const LEVEL_RANK = { insufficiente: -1, nessuno: 0, basso: 1, medio: 2, alto: 3 };

  // ISO 13849-1, allegato F, tab. F.1: misure contro i guasti di causa comune (soglia 65 punti).
  const CCF_MEASURES = [
    { id: 'separazione', punti: 15, testo: 'Separazione fisica tra i percorsi dei segnali' },
    { id: 'diversita', punti: 20, testo: 'Diversità (tecnologie, componenti o principi diversi)' },
    { id: 'sovratensioni', punti: 15, testo: 'Protezione da sovratensioni, sovrapressioni, ecc.' },
    { id: 'collaudati', punti: 5, testo: 'Componenti ben collaudati' },
    { id: 'fmea', punti: 5, testo: 'FMEA per individuare i guasti di causa comune' },
    { id: 'competenza', punti: 5, testo: 'Formazione dei progettisti su CCF' },
    { id: 'emc', punti: 25, testo: 'Compatibilità elettromagnetica verificata' },
    { id: 'ambiente', punti: 10, testo: 'Resistenza a temperatura, urti, vibrazioni, umidità' },
  ];
  const CCF_MIN = 65;
  function ccfScore(sel) {
    return CCF_MEASURES.reduce((s, m) => s + (sel && sel[m.id] ? m.punti : 0), 0);
  }

  // ISO 13849-1, cap. 6.2 e fig. 5: requisiti delle categorie.
  const CATEGORIE = {
    B: { maxPL: 'b', canali: 1, dcMin: null, mttfdMin: 'basso', ccf: false, collaudati: false },
    1: { maxPL: 'c', canali: 1, dcMin: null, mttfdMin: 'alto', ccf: false, collaudati: true },
    2: { maxPL: 'd', canali: 1, dcMin: 'basso', mttfdMin: 'basso', ccf: true, collaudati: false },
    3: { maxPL: 'e', canali: 2, dcMin: 'basso', mttfdMin: 'basso', ccf: true, collaudati: false },
    4: { maxPL: 'e', canali: 2, dcMin: 'alto', mttfdMin: 'alto', ccf: true, collaudati: false },
  };

  // ISO 13849-1, allegato K, tab. K.1: PFH [1/h] per MTTFd di ogni canale, categoria e DCavg.
  // Trascritta da "Calcolo Performance Level" (Wide Automation, 2021), che riporta la tabella della norma;
  // il test verifica ogni valore contro la colonna PL della tabella. Colonne: B (DC nessuna, 3–27 anni),
  // 1 (DC nessuna, 30–100), 2 e 3 con DC bassa/media, 4 con DC alta (30–100). null = combinazione non prevista.
  const K1_MTTFD = [3, 3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1, 10, 11, 12, 13, 15, 16, 18, 20, 22, 24, 27,
    30, 33, 36, 39, 43, 47, 51, 56, 62, 68, 75, 82, 91, 100];
  const K1_COLONNE = ['B', '1', '2/basso', '2/medio', '3/basso', '3/medio', '4/alto'];
  const K1_RIGHE = [
    // B        1        2 bassa  2 media  3 bassa  3 media  4 alta
    ['3.80e-5', null, '2.58e-5', '1.99e-5', '1.26e-5', '6.09e-6', null],
    ['3.46e-5', null, '2.33e-5', '1.79e-5', '1.13e-5', '5.41e-6', null],
    ['3.17e-5', null, '2.13e-5', '1.62e-5', '1.03e-5', '4.86e-6', null],
    ['2.93e-5', null, '1.95e-5', '1.48e-5', '9.37e-6', '4.40e-6', null],
    ['2.65e-5', null, '1.76e-5', '1.33e-5', '8.39e-6', '3.89e-6', null],
    ['2.43e-5', null, '1.60e-5', '1.20e-5', '7.58e-6', '3.48e-6', null],
    ['2.24e-5', null, '1.47e-5', '1.10e-5', '6.91e-6', '3.15e-6', null],
    ['2.04e-5', null, '1.33e-5', '9.87e-6', '6.21e-6', '2.80e-6', null],
    ['1.84e-5', null, '1.19e-5', '8.80e-6', '5.53e-6', '2.47e-6', null],
    ['1.68e-5', null, '1.08e-5', '7.93e-6', '4.98e-6', '2.20e-6', null],
    ['1.52e-5', null, '9.75e-6', '7.10e-6', '4.45e-6', '1.95e-6', null],
    ['1.39e-5', null, '8.87e-6', '6.43e-6', '4.02e-6', '1.74e-6', null],
    ['1.25e-5', null, '7.94e-6', '5.71e-6', '3.57e-6', '1.53e-6', null],
    ['1.14e-5', null, '7.18e-6', '5.14e-6', '3.21e-6', '1.36e-6', null],
    ['1.04e-5', null, '6.44e-6', '4.53e-6', '2.81e-6', '1.18e-6', null],
    ['9.51e-6', null, '5.84e-6', '4.04e-6', '2.49e-6', '1.04e-6', null],
    ['8.78e-6', null, '5.33e-6', '3.64e-6', '2.23e-6', '9.21e-7', null],
    ['7.61e-6', null, '4.53e-6', '3.01e-6', '1.82e-6', '7.44e-7', null],
    ['7.13e-6', null, '4.21e-6', '2.77e-6', '1.67e-6', '6.76e-7', null],
    ['6.34e-6', null, '3.68e-6', '2.37e-6', '1.41e-6', '5.67e-7', null],
    ['5.71e-6', null, '3.26e-6', '2.06e-6', '1.22e-6', '4.85e-7', null],
    ['5.19e-6', null, '2.93e-6', '1.82e-6', '1.07e-6', '4.21e-7', null],
    ['4.76e-6', null, '2.65e-6', '1.62e-6', '9.47e-7', '3.70e-7', null],
    ['4.23e-6', null, '2.32e-6', '1.39e-6', '8.04e-7', '3.10e-7', null],
    [null, '3.80e-6', '2.06e-6', '1.21e-6', '6.94e-7', '2.65e-7', '9.54e-8'],
    [null, '3.46e-6', '1.85e-6', '1.06e-6', '5.94e-7', '2.30e-7', '8.57e-8'],
    [null, '3.17e-6', '1.67e-6', '9.39e-7', '5.16e-7', '2.01e-7', '7.77e-8'],
    [null, '2.93e-6', '1.53e-6', '8.40e-7', '4.53e-7', '1.78e-7', '7.11e-8'],
    [null, '2.65e-6', '1.37e-6', '7.34e-7', '3.87e-7', '1.54e-7', '6.37e-8'],
    [null, '2.43e-6', '1.24e-6', '6.49e-7', '3.35e-7', '1.34e-7', '5.76e-8'],
    [null, '2.24e-6', '1.13e-6', '5.80e-7', '2.93e-7', '1.19e-7', '5.26e-8'],
    [null, '2.04e-6', '1.02e-6', '5.10e-7', '2.52e-7', '1.03e-7', '4.73e-8'],
    [null, '1.84e-6', '9.06e-7', '4.43e-7', '2.13e-7', '8.84e-8', '4.22e-8'],
    [null, '1.68e-6', '8.17e-7', '3.90e-7', '1.84e-7', '7.68e-8', '3.80e-8'],
    [null, '1.52e-6', '7.31e-7', '3.40e-7', '1.57e-7', '6.62e-8', '3.41e-8'],
    [null, '1.39e-6', '6.61e-7', '3.01e-7', '1.35e-7', '5.79e-8', '3.08e-8'],
    [null, '1.25e-6', '5.88e-7', '2.61e-7', '1.14e-7', '4.94e-8', '2.74e-8'],
    [null, '1.14e-6', '5.28e-7', '2.29e-7', '1.01e-7', '4.29e-8', '2.47e-8'],
  ];
  const K1_FONTE = 'ISO 13849-1, all. K, tab. K.1 (trascritta da "Calcolo Performance Level", Wide Automation, 2021)';

  // PFH dalla tab. K.1: riga con MTTFd immediatamente inferiore o uguale (conservativo).
  // Restituisce { nano, riga, colonna, fonte, note[] } oppure { errore }.
  function pfhK1(categoria, dcLev, mttfd) {
    if (!CATEGORIE[categoria]) return { errore: 'categoria non scelta' };
    if (!(mttfd >= 3)) return { errore: 'MTTFd sotto 3 anni o non calcolato' };
    const note = [];
    let dc = null;
    if (categoria === '2' || categoria === '3') {
      if (dcLev === 'basso' || dcLev === 'medio') dc = dcLev;
      else if (dcLev === 'alto') { dc = 'medio'; note.push(`manca la colonna DC alta per la cat. ${categoria}, usata la DC media`); }
      else return { errore: `la cat. ${categoria} richiede DCavg almeno bassa` };
    } else if (categoria === '4') {
      if (dcLev !== 'alto') return { errore: 'la cat. 4 richiede DCavg alta' };
      dc = 'alto';
    }
    const colonna = dc ? `${categoria}/${dc}` : categoria;
    const j = K1_COLONNE.indexOf(colonna);
    let i = -1;
    for (let k = 0; k < K1_MTTFD.length; k++) if (K1_MTTFD[k] <= mttfd + 1e-9 && K1_RIGHE[k][j] != null) i = k;
    if (i < 0) return { errore: `nessun valore in tab. K.1 per cat. ${categoria} con MTTFd ${mttfd.toFixed(1)} anni` };
    const riga = K1_MTTFD[i];
    if (categoria === 'B' && mttfd > 27) note.push('la cat. B arriva a MTTFd medio, usata la riga 27 anni');
    if (categoria === '4' && mttfd > 100) note.push('la tabella trascritta arriva a 100 anni, usata la riga 100 anni (conservativo)');
    const nano = Math.round(Number(K1_RIGHE[i][j]) * 1e9 * 1000) / 1000;
    return { nano, riga, colonna, note, fonte: `${K1_FONTE}, cat. ${categoria}${dc ? ', DCavg ' + dc.replace(/o$/, 'a') : ''}, riga MTTFd ${String(riga).replace('.', ',')} anni` };
  }

  function seriesMttfd(items) {
    const inv = items.reduce((s, c) => s + c.qty / c.mttfd, 0);
    return inv > 0 ? 1 / inv : null;
  }
  // ISO 13849-1, allegato D, eq. D.2: simmetrizzazione di due canali diversi.
  function symmetrize(a, b) {
    if (a == null || b == null) return a ?? b;
    return (2 / 3) * (a + b - 1 / (1 / a + 1 / b));
  }

  function evalSubsystem(ss, articoli, missionTime) {
    const mt = missionTime || 20;
    const errors = [], warns = [];
    const find = id => articoli.find(a => a.id === id);
    const comps = (ss.componenti || []).map(c => ({ c, a: find(c.articoloId), qty: c.qty ?? 1 }));
    if (!comps.length) warns.push('Nessun componente scelto.');
    for (const { c, a } of comps) {
      if (!a) errors.push(`Articolo "${c.articoloId}" non trovato nell'archivio.`);
      else if (!a.fonte) warns.push(`${a.codice}: manca la fonte del dato.`);
    }

    if (ss.metodo !== 'arch') {
      let nano = 0, cap = null;
      for (const { a, qty } of comps) {
        if (!a) continue;
        if (a.pfh == null) warns.push(`${a.codice}: PFH non inserito, considerato 0.`);
        else nano += qty * a.pfh;
        if (a.plMax) cap = plMin(cap, a.plMax);
      }
      const pl = plMin(toPL(nano * 1e-9).pl, cap);
      return { metodo: 'pfh', nano, pl, errors, warns };
    }

    // Architettura designata: MTTFd per canale, DCavg, categoria, CCF, PFH da tab. K.1.
    const cat = CATEGORIE[ss.categoria];
    if (!cat) errors.push('Categoria non scelta.');
    const items = [];
    for (const { c, a, qty } of comps) {
      if (!a) continue;
      let mttfd = a.mttfd ?? null, t10 = null;
      if (mttfd == null && a.b10d != null) {
        if (c.dop > 0 && c.hop > 0 && c.tcycle > 0) {
          const n = nop(c.dop, c.hop, c.tcycle);
          mttfd = b10dToMttfd(a.b10d, n);
          t10 = t10d(a.b10d, n);
          if (t10 < mt) warns.push(`${a.codice}: T10d = ${t10.toFixed(1)} anni, inferiore alla mission time: va sostituito prima.`);
        } else warns.push(`${a.codice}: inserisci giorni/anno, ore/giorno e tempo ciclo per calcolare MTTFd da B10d.`);
      }
      if (mttfd == null) { warns.push(`${a.codice}: né MTTFd né B10d disponibili, componente escluso dal calcolo.`); continue; }
      if (c.dc == null) warns.push(`${a.codice}: DC non inserita, considerata 0 %.`);
      items.push({ codice: a.codice, canale: c.canale === 2 ? 2 : 1, qty, mttfd, dc: c.dc ?? 0, t10 });
    }
    const ch1 = seriesMttfd(items.filter(i => i.canale === 1));
    let ch2 = seriesMttfd(items.filter(i => i.canale === 2));
    if (cat && cat.canali === 2 && ch2 == null && ch1 != null) {
      warns.push('Categoria a due canali ma nessun componente sul canale 2: considerato uguale al canale 1.');
      ch2 = ch1;
    }
    const cap = ss.categoria === '4' ? 2500 : 100; // tab. 5, nota per la categoria 4
    let mttfd = cat && cat.canali === 2 ? symmetrize(ch1, ch2) : ch1;
    if (mttfd != null && mttfd > cap) mttfd = cap;
    const den = items.reduce((s, i) => s + i.qty / i.mttfd, 0);
    const dcavg = den > 0 ? items.reduce((s, i) => s + (i.qty * i.dc) / i.mttfd, 0) / den : null;
    const mLev = mttfd == null ? null : mttfdLevel(mttfd);
    const dLev = dcavg == null ? null : dcLevel(dcavg);
    const ccf = ccfScore(ss.ccf);

    if (cat) {
      if (mLev === 'insufficiente') errors.push(`MTTFd ${mttfd.toFixed(1)} anni: sotto 3 anni non è ammesso.`);
      else if (mLev && LEVEL_RANK[mLev] < LEVEL_RANK[cat.mttfdMin]) errors.push(`Categoria ${ss.categoria}: MTTFd almeno "${cat.mttfdMin}", ottenuto "${mLev}".`);
      if (cat.dcMin && dLev && LEVEL_RANK[dLev] < LEVEL_RANK[cat.dcMin]) errors.push(`Categoria ${ss.categoria}: DCavg almeno "${cat.dcMin}", ottenuta "${dLev}" (${dcavg.toFixed(1)} %).`);
      if (cat.ccf && ccf < CCF_MIN) errors.push(`Categoria ${ss.categoria}: CCF ${ccf} punti, ne servono almeno ${CCF_MIN}.`);
      if (cat.collaudati && !ss.collaudati) errors.push('Categoria 1: i componenti devono essere ben collaudati.');
    }
    const k1 = cat && mLev && mLev !== 'insufficiente' ? pfhK1(ss.categoria, dLev, mttfd) : null;
    if (k1 && k1.note) for (const n of k1.note) warns.push(`Tab. K.1: ${n}.`);
    const manuale = ss.pfhK1 ?? null;
    const nano = manuale ?? (k1 && !k1.errore ? k1.nano : null);
    if (manuale != null && k1 && !k1.errore && Math.abs(manuale - k1.nano) > 1e-6 * Math.max(1, k1.nano))
      warns.push(`PFH inserito a mano (${manuale}) diverso dalla tab. K.1 (${k1.nano}): vale quello a mano. Svuota il campo per usare la tabella.`);
    if (nano == null) warns.push(k1 && k1.errore ? `PFH non ricavabile dalla tab. K.1: ${k1.errore}.` : 'PFH non disponibile: completa categoria, componenti e DC.');
    if (cat && cat.canali === 1 && items.some(i => i.canale === 2))
      warns.push(`Categoria ${ss.categoria} a un solo canale: i componenti sul canale 2 non entrano nel calcolo. Per due canali scegli la categoria 3 o 4.`);
    const plPfh = nano == null ? null : toPL(nano * 1e-9).pl;
    if (plPfh && cat && PL_RANK[plPfh] > PL_RANK[cat.maxPL])
      warns.push(`PL limitato a ${cat.maxPL} dalla categoria ${ss.categoria} (dal PFH sarebbe ${plPfh}).`);
    const pl = plPfh == null ? null : plMin(plPfh, cat ? cat.maxPL : null);
    return { metodo: 'arch', nano, pl, k1: k1 && !k1.errore ? k1 : null, pfhManuale: manuale != null, ch1, ch2, mttfd, mttfdLevel: mLev, dcavg, dcLevel: dLev, ccf, items, errors, warns };
  }

  // Sottosistemi senza percorso sono comuni; quelli con un percorso sono iniziatori alternativi (OR):
  // ogni percorso = comuni + i suoi, in serie. La funzione ha il PL del percorso peggiore.
  function evalFunction(fn, articoli, missionTime) {
    const req = plr(fn.S, fn.F, fn.P);
    const subs = (fn.sottosistemi || []).map(ss => ({ ss, r: evalSubsystem(ss, articoli, missionTime) }));
    const names = [...new Set(subs.map(x => (x.ss.percorso || '').trim()).filter(Boolean))];
    const groups = names.length ? names : [''];
    const paths = groups.map(nome => {
      const chain = subs.filter(x => !(x.ss.percorso || '').trim() || x.ss.percorso.trim() === nome);
      const nano = chain.reduce((s, x) => s + (x.r.nano || 0), 0);
      const complete = chain.length > 0 && chain.every(x => x.r.pl != null);
      let pl = complete ? toPL(nano * 1e-9).pl : null;
      if (complete) for (const x of chain) pl = plMin(pl, x.r.pl); // ISO 13849-1, 6.3
      return { nome: nome || 'unico', nano, pl, complete, sottosistemi: chain.map(x => x.ss.nome) };
    });
    const worst = paths.reduce((w, p) => {
      if (!w) return p;
      if (p.pl == null || w.pl == null) return p.pl == null ? p : w;
      return PL_RANK[p.pl] < PL_RANK[w.pl] || (p.pl === w.pl && p.nano > w.nano) ? p : w;
    }, null);
    const errors = subs.flatMap(x => x.r.errors.map(e => `${x.ss.nome}: ${e}`));
    const warns = subs.flatMap(x => x.r.warns.map(e => `${x.ss.nome}: ${e}`));
    if (!req) warns.push('PLr non definito: completa S, F e P.');
    const missing = ['rilevamento', 'logica', 'attuazione'].filter(ruolo => !subs.some(x => x.ss.ruolo === ruolo));
    if (missing.length) warns.push(`Funzione incompleta: manca un sottosistema di ${missing.join(', ')}.`);
    const pl = worst ? worst.pl : null;
    const ok = !!(req && pl && worst.complete && !missing.length && !errors.length && plAtLeast(pl, req));
    return { plr: req, subs, paths, worst, pl, ok, errors, warns };
  }

  return {
    PL_LIMITS, toPL, plMin, plAtLeast, plr, nop, b10dToMttfd, t10d, mttfdLevel, dcLevel,
    CCF_MEASURES, CCF_MIN, ccfScore, CATEGORIE, K1_MTTFD, K1_COLONNE, K1_RIGHE, pfhK1, symmetrize, evalSubsystem, evalFunction,
  };
});
