// Misure contro i guasti sistematici (ISO 13849-1, all. G e requisiti del software di sicurezza), prove
// di validazione delle funzioni (ISO 13849-2) e verifiche elettriche (IEC 60204-1, cap. 18).
// Le prove di ogni funzione si ricavano dallo schema a blocchi; gli esiti stanno in f.validazione.esiti
// per chiave, così una prova resta compilata finché il blocco che l'ha generata esiste.
// Nel browser window.Validazione, in Node module.exports (richiede schema.js).
(function (root, factory) {
  const api = factory(typeof module !== 'undefined' && module.exports ? require('./schema.js') : root.Schema);
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Validazione = api;
})(typeof self !== 'undefined' ? self : this, function (Schema) {
  'use strict';

  const MISURE_SISTEMATICHE = [
    { gruppo: 'Controllo dei guasti sistematici (ISO 13849-1, all. G)', misure: [
      ['deenergia', 'Stato sicuro ottenuto per de-energizzazione'],
      ['alimentazione', 'Effetti di interruzione, sovratensione e sottotensione dell\'alimentazione controllati'],
      ['ambiente', 'Condizioni ambientali (temperatura, umidità, vibrazioni, polvere) ed EMC compatibili con i dati dei componenti'],
      ['trasmissione', 'Errori della trasmissione dati controllati (es. PROFIsafe)'],
      ['contatti', 'Contatti a guida forzata o ad apertura diretta dove richiesto'],
    ] },
    { gruppo: 'Prevenzione dei guasti sistematici (ISO 13849-1, all. G)', misure: [
      ['componenti', 'Componenti scelti, dimensionati e installati secondo le istruzioni del costruttore'],
      ['cablaggio', 'Cablaggio protetto da errori e cortocircuiti (canali separati, rilevamento dei cortocircuiti tra canali)'],
      ['revisione', 'Progetto (schemi elettrici, parametri) rivisto da una persona diversa dal progettista'],
      ['documentazione', 'Schemi e documentazione aggiornati alla revisione di questo documento'],
    ] },
    { gruppo: 'Software di sicurezza (ISO 13849-1, SRASW)', misure: [
      ['sw-specifica', 'Specifica dei requisiti del software di sicurezza documentata'],
      ['sw-librerie', 'Blocchi funzionali di sicurezza certificati del costruttore'],
      ['sw-struttura', 'Programma modulare e strutturato, linguaggio a variabilità limitata (FBD/LAD)'],
      ['sw-review', 'Revisione del codice'],
      ['sw-test', 'Test funzionali del programma documentati'],
      ['sw-versioni', 'Gestione delle versioni e analisi d\'impatto delle modifiche'],
      ['sw-firma', 'Firma del programma F e stampa di accettazione archiviate'],
    ] },
  ];

  // Verifiche dell'equipaggiamento elettrico (IEC 60204-1:2016, cap. 18). I criteri sono riassunti dalla norma
  // con la clausola; vanno confrontati con la copia della norma in uso (stessa regola dei valori di catalogo).
  const FONTE_ELETTRICHE = 'IEC 60204-1:2016 (EN 60204-1:2018), cap. 18';
  const PROVE_ELETTRICHE = [
    { key: 'continuita', clausola: '18.2.2', testo: 'Continuità del circuito di protezione equipotenziale (prova 1)',
      criterio: 'Continuità verificata tra il morsetto PE e ogni parte del circuito di protezione', unita: 'Ω' },
    { key: 'anello', clausola: '18.2.3', testo: 'Impedenza dell\'anello di guasto e protezione per interruzione automatica (prova 2)',
      criterio: 'Impedenza compatibile con l\'intervento del dispositivo di protezione nei tempi richiesti (6.3.3, all. A)', unita: 'Ω' },
    { key: 'isolamento', clausola: '18.3', testo: 'Resistenza di isolamento tra i conduttori dei circuiti di potenza e il circuito di protezione',
      criterio: '500 V c.c.; non inferiore a 1 MΩ', unita: 'MΩ' },
    { key: 'tensione', clausola: '18.4', testo: 'Prova di tensione (rigidità dielettrica)',
      criterio: '2 × tensione nominale o 1000 V (il maggiore), 50/60 Hz per circa 1 s; nessuna scarica. Scollegare i componenti non adatti', unita: 'V' },
    { key: 'residue', clausola: '18.5', testo: 'Protezione contro le tensioni residue',
      criterio: 'Parti attive accessibili sotto 60 V entro 5 s dall\'interruzione dell\'alimentazione (6.2.4)', unita: 'V' },
    { key: 'funzionali', clausola: '18.6', testo: 'Prove funzionali dei circuiti elettrici, in particolare di quelli di sicurezza',
      criterio: 'Esito delle prove di validazione delle funzioni di sicurezza (ISO 13849-2)', unita: '' },
  ];

  // Prove elettriche standard + punti di misura aggiunti a mano, con valore misurato ed esito
  function proveElettriche(el) {
    const e = el || {};
    const esiti = e.esiti || {};
    return [...PROVE_ELETTRICHE, ...(e.extra || []).map(p => ({ key: 'extra:' + p.id, testo: p.testo, criterio: p.criterio, unita: p.unita, extra: p }))]
      .map(p => ({ ...p, ...(esiti[p.key] || {}) }));
  }

  // Registro delle misure sul campo (come il foglio misure dei tecnici): collegamenti equipotenziali
  // per la 18.2.2 e un cavo per riga per 18.2.2 (RPE), 18.2.3 (Zs) e 18.3 (isolamento). Valori come testo
  // ("0,004", ">1", "<0,1"), così resta quello che il tecnico ha scritto.
  const COLONNE_EQUI = [['punto', 'Collegamento (da/a)'], ['conduttore', 'Conduttore'], ['sezione', 'Sezione [mm²]'], ['rpe', 'R [Ω]'], ['note', 'Note']];
  const ISO = [['l1pe', 'L1-PE'], ['l2pe', 'L2-PE'], ['l3pe', 'L3-PE'], ['l1l2', 'L1-L2'], ['l1l3', 'L1-L3'], ['l2l3', 'L2-L3']];
  const COLONNE_CAVI = [['sigla', 'Sigla'], ['percorso', 'Da/a'], ['tipo', 'Tipo cavo'], ['formazione', 'Formazione'], ['sezione', 'Sez. [mm²]'],
    ['protezione', 'Protezione'], ['in', 'In [A]'], ['zs', 'Zs [Ω]'], ...ISO, ['rpe', 'RPE [Ω]'], ['note', 'Note']];
  const MISURE_CAVI = ['zs', ...ISO.map(c => c[0]), 'rpe']; // le colonne che compila il tecnico
  const ISO_MIN = 1; // MΩ, 18.3 (vedi criterio della prova)

  // "0,004" → { op: '', v: 0.004 }, ">1" → { op: '>', v: 1 }; vuoto → null; testo non numerico → { v: NaN }
  function leggiMisura(t) {
    const m = String(t ?? '').trim().replace(/\s+/g, '').match(/^([<>≤≥]?)=?(.*)$/);
    if (!m[2]) return null;
    const n = m[2].replace(',', '.');
    return { op: m[1].replace('≤', '<').replace('≥', '>'), v: /^(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(n) ? Number(n) : NaN };
  }

  // Esito dell'isolamento di un cavo: 'ok' se ogni valore scritto è ≥ 1 MΩ, 'ko' se uno è sotto, '' se mancano
  function esitoIsolamento(cavo) {
    const mis = ISO.map(([k]) => leggiMisura(cavo[k])).filter(Boolean);
    if (!mis.length) return '';
    return mis.every(m => !isNaN(m.v) && m.op !== '<' && m.v >= ISO_MIN) ? 'ok' : 'ko';
  }

  const peggiore = (valori, alto) => valori.filter(m => m && !isNaN(m.v))
    .reduce((p, m) => (!p || (alto ? m.v > p.v : m.v < p.v) ? m : p), null);
  const testo = m => (m ? m.op + String(m.v).replace('.', ',') : null);

  // Riepilogo del registro per le righe 18.2.2, 18.2.3 e 18.3 del report
  function riepilogoRegistro(el) {
    const equi = (el && el.equipotenziali) || [];
    const cavi = (el && el.cavi) || [];
    const misurato = c => MISURE_CAVI.some(k => leggiMisura(c[k]));
    return {
      equipotenziali: equi.length, cavi: cavi.length,
      rpeMax: testo(peggiore([...equi, ...cavi].map(r => leggiMisura(r.rpe)), true)),
      zsMax: testo(peggiore(cavi.map(c => leggiMisura(c.zs)), true)),
      isoMin: testo(peggiore(cavi.flatMap(c => ISO.map(([k]) => leggiMisura(c[k]))), false)),
      isoKo: cavi.filter(c => esitoIsolamento(c) === 'ko').map(c => c.sigla || '?'),
      senzaMisure: cavi.filter(c => !misurato(c)).length + equi.filter(r => !leggiMisura(r.rpe)).length,
    };
  }

  // Righe incollate da Excel/Calc (tabulazioni o punto e virgola) nell'ordine delle colonne; salta l'intestazione
  function daTesto(txt, colonne) {
    return String(txt || '').split(/\r?\n/).map(r => r.split(r.includes('\t') ? '\t' : ';').map(x => x.trim()))
      .filter(c => c.some(Boolean) && !(c[0] || '').toLowerCase().startsWith(colonne[0][1].toLowerCase().slice(0, 5)))
      .map(c => Object.fromEntries(colonne.map(([k], i) => [k, c[i] || ''])));
  }

  const ESITI = [['', '—'], ['ok', 'OK'], ['ko', 'Non OK'], ['na', 'Non applicabile']];

  const elenco = nomi => nomi.filter(Boolean).join(', ') || '—';

  // Prove standard di una funzione, nell'ordine dello schema: una prova funzionale per percorso,
  // tempo di risposta e reset, poi per ogni blocco l'iniezione dei guasti (architettura designata,
  // cat. 2, 3, 4) o il controllo della parametrizzazione (PFH da certificato).
  function proveAuto(f) {
    const nomi = Schema.percorsi(f);
    const prove = nomi.map(nome => {
      const iniziatori = Schema.catena(f, nome).filter(ss => ss.ruolo === 'rilevamento').map(ss => ss.nome);
      return { key: 'funz:' + nome, testo: (nome ? `${nome}: attivare ` : 'Attivare ') + `ogni dispositivo di comando o rilevamento (${elenco(iniziatori)})`,
        atteso: 'Raggiunto lo stato sicuro previsto dalla funzione' };
    });
    prove.push(
      { key: 'tempo', testo: 'Misurare il tempo di risposta fino allo stato sicuro', atteso: 'Entro il tempo richiesto dalla valutazione dei rischi' },
      { key: 'reset', testo: 'Ripristinare il comando dopo l\'intervento', atteso: 'Nessun riavvio automatico: serve un reset manuale' });
    for (const g of Schema.gruppi(f)) for (const ss of g.blocchi) {
      if (ss.metodo === 'arch' && ['3', '4'].includes(ss.categoria)) {
        prove.push(
          { key: `guasto:${ss.id}`, testo: `${ss.nome}: simulare un guasto su un canale (contatto incollato o filo interrotto)`,
            atteso: 'Guasto rilevato, funzione mantenuta, riavvio impedito fino alla riparazione' },
          { key: `corto:${ss.id}`, testo: `${ss.nome}: simulare un cortocircuito tra i due canali`, atteso: 'Cortocircuito rilevato, stato sicuro' });
      } else if (ss.metodo === 'arch' && ss.categoria === '2') {
        prove.push({ key: `guasto:${ss.id}`, testo: `${ss.nome}: simulare un guasto e attendere il test periodico`,
          atteso: 'Guasto rilevato dal test, stato sicuro o segnalazione' });
      } else if (ss.metodo === 'pfh') {
        prove.push({ key: `param:${ss.id}`, testo: `${ss.nome}: confrontare parametri e cablaggio con il manuale e il certificato del costruttore`,
          atteso: 'Parametri conformi (es. tempo di discrepanza, parametri F)' });
      }
    }
    return prove;
  }

  // Prove standard + prove aggiunte a mano, ognuna con il suo esito
  function prove(f) {
    const v = f.validazione || {};
    const esiti = v.esiti || {};
    return [...proveAuto(f), ...(v.extra || []).map(p => ({ key: 'extra:' + p.id, testo: p.testo, atteso: p.atteso, extra: p }))]
      .map(p => ({ ...p, ...(esiti[p.key] || {}) }));
  }

  // Validazione completa quando ogni prova applicabile è OK
  function riepilogo(lista) {
    const conta = e => lista.filter(p => (p.esito || '') === e).length;
    const r = { totali: lista.length, ok: conta('ok'), ko: conta('ko'), na: conta('na'), aperte: conta('') };
    r.completa = r.totali > 0 && r.ko === 0 && r.aperte === 0;
    return r;
  }

  return { MISURE_SISTEMATICHE, ESITI, FONTE_ELETTRICHE, PROVE_ELETTRICHE, COLONNE_EQUI, COLONNE_CAVI, ISO, MISURE_CAVI, ISO_MIN,
    proveAuto, prove, proveElettriche, riepilogo, leggiMisura, esitoIsolamento, riepilogoRegistro, daTesto };
});
