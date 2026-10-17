// Lettore dei database dei costruttori nel formato VDMA 66413 (file XML, es. vdma.xml di Siemens).
// Ogni "use case" di un dispositivo diventa un articolo: stesso codice, condizioni d'uso diverse.
// Nel browser espone window.Vdma, in Node module.exports. Nessuna dipendenza.
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Vdma = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  class FormatError extends Error {}

  const NOTA = 'Importato da database VDMA 66413: confrontare con la documentazione del costruttore prima dell\'uso.';
  const LINGUE = ['it', 'en', 'de'];
  const PL = { PL_a: 'a', PL_b: 'b', PL_c: 'c', PL_d: 'd', PL_e: 'e' };

  // ---- XML minimo: elementi, attributi, testo, entità. Basta per VDMA 66413 e funziona anche in Node. ----
  const ENT = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" };
  const unescape = s => s.replace(/&(#x[0-9a-f]+|#\d+|\w+);/gi, (m, e) =>
    e[0] === '#' ? String.fromCodePoint(e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10)) : (ENT[e] ?? m));

  function parseXml(text) {
    const rootNode = { tag: '#root', attrs: {}, children: [], text: '' };
    const stack = [rootNode];
    const re = /<!--[\s\S]*?-->|<!\[CDATA\[([\s\S]*?)\]\]>|<[?!][\s\S]*?>|<\/([^\s>]+)\s*>|<([^\s/>]+)((?:\s+[^\s=]+\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>|([^<]+)/g;
    let m;
    while ((m = re.exec(text))) {
      const top = stack[stack.length - 1];
      if (m[1] != null) top.text += m[1];
      else if (m[2]) {
        if (top.tag !== m[2]) throw new FormatError(`XML non valido: </${m[2]}> chiude <${top.tag}>`);
        stack.pop();
      } else if (m[3]) {
        const attrs = {};
        m[4].replace(/([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g, (_, k, a, b) => { attrs[k] = unescape(a ?? b); });
        const el = { tag: m[3], attrs, children: [], text: '' };
        top.children.push(el);
        if (!m[5]) stack.push(el);
      } else if (m[6] != null) top.text += unescape(m[6]);
    }
    if (stack.length !== 1) throw new FormatError(`XML non valido: <${stack[stack.length - 1].tag}> non chiuso`);
    return rootNode;
  }
  const kid = (el, tag) => el && el.children.find(c => c.tag === tag);
  const kids = (el, tag) => (el ? el.children.filter(c => c.tag === tag) : []);
  const txt = (el, tag) => { const c = kid(el, tag); return c ? c.text.trim() : ''; };
  const num = s => { if (s == null || s === '') return null; const v = Number(String(s).trim().replace(',', '.')); return Number.isFinite(v) ? v : null; };

  const pulisci = s => String(s || '').replace(/\s+/g, ' ').trim();
  const slug = s => (s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 20)) || 'vdma';
  // FNV-1a a 32 bit: id stabile e breve a partire dall'Identifier del dispositivo
  function hash(s) {
    let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
    return (h >>> 0).toString(36);
  }

  // Legge il testo di un file VDMA 66413 e restituisce { libreria, articoli, scartati }
  function importa(text) {
    const doc = parseXml(String(text).replace(/^﻿/, ''));
    const vdma = kid(doc, 'VDMA66413');
    const man = kid(vdma, 'Manufacturer');
    if (!man) throw new FormatError('Il file non è un database VDMA 66413 (manca <VDMA66413><Manufacturer>).');

    // testi tradotti: sezione → chiave → testo nella prima lingua disponibile (it, en, de)
    const lang = kid(man, 'Language');
    const dict = {};
    for (const sec of lang ? lang.children : []) {
      const d = dict[sec.tag] = {};
      for (const e of sec.children) {
        const t = {};
        for (const x of kids(e, 'Text')) t[x.attrs.LanguageKey] = pulisci(x.text);
        d[e.attrs.Key] = LINGUE.map(l => t[l]).find(Boolean) || Object.values(t).find(Boolean) || '';
      }
    }
    const tr = (sec, el) => { const k = el && el.attrs.Key; return k && !k.startsWith('#') ? (dict[sec] && dict[sec][k]) || '' : ''; };

    const produttore = pulisci(txt(man, 'Name')) || 'Costruttore sconosciuto';
    const versione = pulisci(man.attrs.Version || vdma.attrs.Version || '');
    const nomeFile = pulisci(txt(man, 'DBFileName')) || 'vdma.xml';
    const libreria = `VDMA ${nomeFile} ${versione}`.trim();
    const lib = `${produttore}, database VDMA 66413 "${nomeFile}" versione ${versione}`;
    const pref = slug(produttore.split(' ')[0]);
    const articoli = [], scartati = [];

    for (const dev of kids(kid(man, 'Devices'), 'Device')) {
      const ident = pulisci(txt(dev, 'Identifier'));
      const nome = tr('Names', kid(dev, 'Name')) || ident;
      const codice = pulisci(txt(dev, 'PartNumber')) || nome;
      const gruppo = tr('Groups', kid(dev, 'Group'));
      const doc = tr('DocFiles', kid(dev, 'DocFile'));
      const archivio = txt(dev, 'Archive') === 'true';
      const icona = pulisci(txt(dev, 'IconFileName'));
      kids(kid(dev, 'UseCases'), 'UseCase').forEach((uc, i) => {
        const cond = kid(uc, 'Constraints') ? kid(uc, 'Constraints').children.map(h => tr('Constraints', h)).filter(Boolean) : [];
        const fn = kid(uc, 'Function');
        const tipo = txt(fn, 'LogicFunction') === 'true' ? 'logica' : txt(fn, 'OutputFunction') === 'true' ? 'attuatore' : 'sensore';
        const cat = txt(uc, 'InfoConfig').replace(/^CAT_/, '');
        const par = kid(uc, 'Parameter') && kid(uc, 'Parameter').children[0];
        const descrizione = nome + (cond.length ? ' · ' + cond.join(' · ') : '');
        const a = {
          id: `${pref}-${slug(codice)}-${hash(ident)}-${i + 1}`, codice, descrizione, produttore, tipo,
          pfh: null, b10d: null, mttfd: null, plMax: null, dataFonte: '', verificato: false,
          note: NOTA + (archivio ? ' Articolo segnato nel database come non più a catalogo.' : ''),
          libreria, gruppo,
        };
        if (icona) a.icona = icona; // nome del file immagine nel pacchetto del costruttore
        const g = k => num(txt(par, k));
        const rdf = g('RDF');
        let calcolo = '';
        if (par && par.tag === 'DeviceType1' && g('PFH_d') > 0) {
          a.pfh = Math.round(g('PFH_d') * 1e9 * 1e6) / 1e6; // 1/h → 10⁻⁹/h
          a.plMax = PL[txt(par, 'PL')] || null;
        } else if (par && g('B10d') > 0) a.b10d = g('B10d');
        else if (par && g('B10') > 0 && rdf > 0) { a.b10d = Math.round(g('B10') / (rdf / 100)); calcolo = `B10d = B10 / RDF = ${g('B10')} / ${rdf} %`; }
        else if (par && g('MTTF_d') > 0) a.mttfd = g('MTTF_d');
        else if (par && g('MTTF') > 0 && rdf > 0) { a.mttfd = Math.round(g('MTTF') / (rdf / 100) * 10) / 10; calcolo = `MTTFd = MTTF / RDF = ${g('MTTF')} / ${rdf} %`; }
        else { scartati.push([`use case ${i + 1} senza PFH, B10d o MTTFd`, descrizione]); return; }
        const tm = g('TM_T1');
        a.fonte = `${lib}, "${ident}" use case ${i + 1}` + (cat && cat !== 'na' ? `, cat. ${cat}` : '') +
          (tm ? `, mission time ${tm} anni` : '') + (calcolo ? `; ${calcolo}` : '') + (doc ? `; documentazione: ${doc}` : '');
        articoli.push(a);
      });
    }
    return { libreria: `${produttore} · ${libreria}`, articoli, scartati };
  }

  const IMG = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', bmp: 'image/bmp', svg: 'image/svg+xml' };
  const base = s => s.split(/[\\/]/).pop().toLowerCase();

  // Pacchetto .zip del costruttore (database VDMA + immagini). files: [{ nome, leggi() }] da Zip.apri.
  // Restituisce quanto importa() più immagini: Map chiave → { byte, tipo }; ogni articolo con
  // un'immagine trovata riceve immagine = chiave (prefisso costruttore / nome file).
  async function importaPacchetto(files) {
    const xml = files.filter(f => /\.xml$/i.test(f.nome));
    let r = null, errore = null;
    // prima vdma.xml, poi gli altri .xml
    for (const f of xml.sort((a, b) => (base(b.nome) === 'vdma.xml') - (base(a.nome) === 'vdma.xml'))) {
      try { r = importa(new TextDecoder('utf-8').decode(await f.leggi())); r.file = f.nome; break; } catch (e) { errore = e; }
    }
    if (!r) throw errore instanceof FormatError || !errore ? new FormatError('Nello .zip non c\'è un database VDMA 66413 (.xml).') : errore;
    const perNome = new Map(files.filter(f => IMG[f.nome.split('.').pop().toLowerCase()]).map(f => [base(f.nome), f]));
    const immagini = new Map();
    const pref = slug(r.articoli[0] ? r.articoli[0].produttore.split(' ')[0] : 'vdma');
    let mancanti = 0;
    for (const a of r.articoli) {
      if (!a.icona) continue;
      const f = perNome.get(base(a.icona));
      if (!f) { mancanti++; continue; }
      const chiave = `${pref}/${base(a.icona).replace(/[^a-z0-9._-]/g, '_')}`;
      if (!immagini.has(chiave)) immagini.set(chiave, { byte: await f.leggi(), tipo: IMG[f.nome.split('.').pop().toLowerCase()] });
      a.immagine = chiave;
    }
    return { ...r, immagini, immaginiMancanti: mancanti };
  }

  return { importa, importaPacchetto, parseXml, FormatError };
});
