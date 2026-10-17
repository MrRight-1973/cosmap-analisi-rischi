// Lettore delle librerie SISTEMA (.slb) direttamente nel browser, senza driver.
// Una libreria .slb è un database Firebird (ODS 13): qui si leggono le pagine dati,
// si decomprimono i record e si interpretano con i formati salvati nel database stesso.
// Strutture di riferimento: sorgenti Firebird 5 (src/jrd/ods.h, sqz.cpp, relations.h, fields.h, align.h).
// Nel browser espone window.Sistema, in Node module.exports.
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Sistema = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ---- costanti ODS (ods.h) ----
  const PAG_HEADER = 1, PAG_DATA = 5, PAG_BLOB = 6;
  const DPG_SIZE = 24, RHD_SIZE = 13, RHDE_SIZE = 16, RHDF_SIZE = 22, BLH_SIZE = 28, BLP_SIZE = 28;
  const RHD = { deleted: 1, chain: 2, fragment: 4, incomplete: 8, blob: 16, stream: 32, large: 64, damaged: 128, longTra: 1024, notPacked: 2048 };
  // dtype (dsc_pub.h) e allineamenti (align.h)
  const DT = { text: 1, varying: 3, short: 8, long: 9, quad: 10, real: 11, double: 12, date: 14, time: 15, timestamp: 16, blob: 17, int64: 19, boolean: 21 };
  const ALIGN = { 3: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 8, 14: 4, 15: 4, 16: 4, 17: 8, 19: 8, 21: 1 }; // blob: 8 su ODS 13 (verificato sui record)
  const CHARSETS = { 0: 'latin1', 2: 'ascii', 4: 'utf-8', 21: 'latin1', 51: 'windows-1250', 52: 'windows-1251', 53: 'windows-1252' };

  class FormatError extends Error {}

  // Formati delle tabelle di sistema che servono (relations.h + fields.h, ODS 13): [nome, dtype, lunghezza]
  const ID = 252; // MAX_SQL_IDENTIFIER_LEN = 63 caratteri × 4 byte
  const SYS = {
    5: [['RDB$FIELD_NAME', 1, ID], ['RDB$RELATION_NAME', 1, ID], ['RDB$FIELD_SOURCE', 1, ID], ['RDB$QUERY_NAME', 1, ID],
      ['RDB$BASE_FIELD', 1, ID], ['RDB$EDIT_STRING', 3, 129], ['RDB$FIELD_POSITION', 8, 2], ['RDB$QUERY_HEADER', 17, 8],
      ['RDB$UPDATE_FLAG', 8, 2], ['RDB$FIELD_ID', 8, 2], ['RDB$VIEW_CONTEXT', 8, 2], ['RDB$DESCRIPTION', 17, 8],
      ['RDB$DEFAULT_VALUE', 17, 8], ['RDB$SYSTEM_FLAG', 8, 2], ['RDB$SECURITY_CLASS', 1, ID], ['RDB$COMPLEX_NAME', 1, ID],
      ['RDB$NULL_FLAG', 8, 2], ['RDB$DEFAULT_SOURCE', 17, 8], ['RDB$COLLATION_ID', 8, 2], ['RDB$GENERATOR_NAME', 1, ID],
      ['RDB$IDENTITY_TYPE', 8, 2]],
    6: [['RDB$VIEW_BLR', 17, 8], ['RDB$VIEW_SOURCE', 17, 8], ['RDB$DESCRIPTION', 17, 8], ['RDB$RELATION_ID', 8, 2],
      ['RDB$SYSTEM_FLAG', 8, 2], ['RDB$DBKEY_LENGTH', 8, 2], ['RDB$FORMAT', 8, 2], ['RDB$FIELD_ID', 8, 2],
      ['RDB$RELATION_NAME', 1, ID], ['RDB$SECURITY_CLASS', 1, ID], ['RDB$EXTERNAL_FILE', 3, 257], ['RDB$RUNTIME', 17, 8],
      ['RDB$EXTERNAL_DESCRIPTION', 17, 8], ['RDB$OWNER_NAME', 1, ID], ['RDB$DEFAULT_CLASS', 1, ID], ['RDB$FLAGS', 8, 2],
      ['RDB$RELATION_TYPE', 8, 2], ['RDB$SQL_SECURITY', 21, 1]],
    8: [['RDB$RELATION_ID', 8, 2], ['RDB$FORMAT', 8, 2], ['RDB$DESCRIPTOR', 17, 8]],
  };
  function systemFormat(fields) {
    let off = Math.ceil(fields.length / 32) * 4; // FLAG_BYTES: bitmap dei null arrotondata a 32 bit
    return fields.map(([name, dtype, length]) => {
      const a = ALIGN[dtype] || 1;
      off = Math.ceil(off / a) * a;
      const d = { name, dtype, length, subType: dtype === 1 || dtype === 3 ? 4 : 0, scale: 0, offset: off };
      off += length;
      return d;
    });
  }

  // RLE di Firebird (sqz.cpp): n>0 byte letterali; n<0 ripete il byte successivo -n volte;
  // -1 e -2 (ODS 13.1) introducono un contatore a 2 o 4 byte; 0 è riempimento.
  // outLen è la lunghezza minima attesa: il record su disco è arrotondato a 8 byte.
  function decompress(src, outLen) {
    const cap = Math.ceil(outLen / 8) * 8;
    const out = new Uint8Array(cap);
    let i = 0, o = 0;
    while (i < src.length && o < cap) {
      const n = (src[i++] << 24) >> 24;
      if (n > 0) { out.set(src.subarray(i, i + n), o); i += n; o += n; }
      else if (n < 0) {
        let count = -n;
        if (n === -1) { count = src[i] | (src[i + 1] << 8); i += 2; }
        else if (n === -2) { count = (src[i] | (src[i + 1] << 8) | (src[i + 2] << 16)) + src[i + 3] * 16777216; i += 4; }
        if (o + count > cap) break;
        out.fill(src[i++], o, o + count); o += count;
      }
    }
    if (o < outLen || i < src.length) throw new FormatError(`record decompresso di ${o} byte invece di ${outLen}`);
    return out;
  }

  function open(bytes) {
    const buf = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    if (buf.length < 1024 || buf[0] !== PAG_HEADER) throw new FormatError('Il file non è un database Firebird: non sembra una libreria SISTEMA.');
    const pageSize = dv.getUint16(0x10, true);
    const ods = dv.getUint16(0x12, true) & 0x7fff;
    if (ods !== 13) throw new FormatError(`Versione del database non supportata (ODS ${ods}): servono librerie SISTEMA 2.0 o successive.`);
    const nPages = Math.floor(buf.length / pageSize);
    const maxRecs = Math.floor((pageSize - 28) / (4 + RHD_SIZE)); // maxRecsPerDP (ods.cpp)

    // data page per relazione e sequenza
    const dataPages = new Map();
    for (let p = 0; p < nPages; p++) {
      const o = p * pageSize;
      if (buf[o] !== PAG_DATA) continue;
      const rel = dv.getUint16(o + 20, true), seq = dv.getUint32(o + 16, true);
      if (!dataPages.has(rel)) dataPages.set(rel, new Map());
      dataPages.get(rel).set(seq, p);
    }
    const slot = (page, line) => {
      const o = page * pageSize;
      if (buf[o] !== PAG_DATA || line >= dv.getUint16(o + 22, true)) return null;
      const off = dv.getUint16(o + DPG_SIZE + line * 4, true), len = dv.getUint16(o + DPG_SIZE + line * 4 + 2, true);
      return len ? { o: o + off, len } : null;
    };
    const flagsAt = s => dv.getUint16(s.o + 10, true);

    // dati (ancora compressi) di un record, seguendo i frammenti
    function rawRecord(s) {
      let flags = flagsAt(s);
      const format = buf[s.o + 12];
      const parts = [];
      let cur = s;
      for (;;) {
        const f = flagsAt(cur);
        const hs = f & RHD.incomplete ? RHDF_SIZE : f & RHD.longTra ? RHDE_SIZE : RHD_SIZE;
        parts.push(buf.subarray(cur.o + hs, cur.o + cur.len));
        if (!(f & RHD.incomplete)) break;
        const next = slot(dv.getUint32(cur.o + 16, true), dv.getUint16(cur.o + 20, true));
        if (!next) throw new FormatError('frammento di record mancante');
        cur = next;
      }
      const len = parts.reduce((t, p) => t + p.length, 0);
      const data = new Uint8Array(len);
      let k = 0; for (const p of parts) { data.set(p, k); k += p.length; }
      return { flags, format, data };
    }

    // blob (blb.h): livello 0 dati nel record, livello 1 elenco di pagine blob, livello 2 elenco di elenchi
    function readBlob(id) {
      // bid little-endian (RecordNumber.h): relation id, riservato, byte alto del numero, numero
      const relId = id.getUint16(0, true);
      const recNo = id.getUint32(4, true) + id.getUint8(3) * 4294967296;
      if (!relId && !recNo) return null;
      const page = dataPages.get(relId)?.get(Math.floor(recNo / maxRecs));
      const s = page != null && slot(page, recNo % maxRecs);
      if (!s || !(flagsAt(s) & RHD.blob)) throw new FormatError('blob non trovato');
      const level = buf[s.o + 12], length = dv.getUint32(s.o + 20, true);
      const stream = flagsAt(s) & RHD.stream;
      let raw;
      if (level === 0) raw = buf.slice(s.o + BLH_SIZE, s.o + s.len);
      else {
        let pages = [];
        for (let k = s.o + BLH_SIZE; k < s.o + s.len; k += 4) pages.push(dv.getUint32(k, true));
        if (level === 2) pages = pages.flatMap(pp => {
          const o = pp * pageSize, n = dv.getUint16(o + 24, true) / 4, r = [];
          for (let k = 0; k < n; k++) r.push(dv.getUint32(o + BLP_SIZE + k * 4, true));
          return r;
        });
        const chunks = pages.map(pp => { const o = pp * pageSize; return buf.subarray(o + BLP_SIZE, o + BLP_SIZE + dv.getUint16(o + 24, true)); });
        raw = new Uint8Array(chunks.reduce((t, c) => t + c.length, 0));
        let k = 0; for (const c of chunks) { raw.set(c, k); k += c.length; }
      }
      if (stream) return raw.subarray(0, length);
      // blob segmentato: ogni segmento è preceduto dalla sua lunghezza (2 byte)
      const out = new Uint8Array(length); let i = 0, o = 0;
      while (i + 2 <= raw.length && o < length) { const n = raw[i] | (raw[i + 1] << 8); i += 2; out.set(raw.subarray(i, i + n), o); i += n; o += n; }
      return out;
    }

    const decoders = {};
    const decode = (bytes, cs) => (decoders[cs] ||= new TextDecoder(CHARSETS[cs] || 'utf-8')).decode(bytes);

    function decodeRecord(img, fmt) {
      const v = new DataView(img.buffer, img.byteOffset, img.byteLength);
      const row = {};
      fmt.forEach((d, i) => {
        if (!d || !d.name) return;
        if (d.offset + d.length > img.length || img[i >> 3] & (1 << (i & 7))) { row[d.name] = null; return; }
        const o = d.offset;
        switch (d.dtype) {
          case DT.text: row[d.name] = decode(img.subarray(o, o + d.length), d.subType & 0xff).replace(/[\s\0]+$/, ''); break;
          case DT.varying: row[d.name] = decode(img.subarray(o + 2, o + 2 + v.getUint16(o, true)), d.subType & 0xff); break;
          case DT.short: row[d.name] = v.getInt16(o, true) / 10 ** -d.scale; break;
          case DT.long: row[d.name] = v.getInt32(o, true) / 10 ** -d.scale; break;
          case DT.int64: row[d.name] = Number(v.getBigInt64(o, true)) / 10 ** -d.scale; break;
          case DT.real: row[d.name] = v.getFloat32(o, true); break;
          case DT.double: row[d.name] = v.getFloat64(o, true); break;
          case DT.boolean: row[d.name] = !!img[o]; break;
          case DT.date: row[d.name] = new Date((v.getInt32(o, true) - 40587) * 864e5); break;
          case DT.timestamp: row[d.name] = new Date((v.getInt32(o, true) - 40587) * 864e5 + v.getUint32(o + 4, true) / 10); break;
          case DT.blob: row[d.name] = { blob: new DataView(img.buffer, img.byteOffset + o, 8) }; break;
          default: row[d.name] = undefined;
        }
      });
      return row;
    }

    function* records(relId, formatOf) {
      const pages = [...(dataPages.get(relId) || new Map()).entries()].sort((a, b) => a[0] - b[0]);
      for (const [, page] of pages) {
        const n = dv.getUint16(page * pageSize + 22, true);
        for (let line = 0; line < n; line++) {
          const s = slot(page, line);
          if (!s) continue;
          const f = flagsAt(s);
          if (f & (RHD.deleted | RHD.chain | RHD.fragment | RHD.blob)) continue;
          const r = rawRecord(s);
          const fmt = formatOf(r.format);
          if (!fmt) throw new FormatError(`formato ${r.format} della tabella ${relId} non trovato`);
          const len = fmt.reduce((m, d) => Math.max(m, d ? d.offset + d.length : 0), Math.ceil(fmt.length / 32) * 4);
          const img = f & RHD.notPacked ? r.data : decompress(r.data, len);
          yield decodeRecord(img, fmt);
        }
      }
    }

    // tabelle di sistema → nomi, campi e formati delle tabelle utente
    const sys = id => { const f = systemFormat(SYS[id]); return () => f; };
    const relIds = new Map();
    for (const r of records(6, sys(6))) relIds.set(r['RDB$RELATION_NAME'], r['RDB$RELATION_ID']);
    const fieldNames = new Map();
    for (const r of records(5, sys(5))) {
      if (!fieldNames.has(r['RDB$RELATION_NAME'])) fieldNames.set(r['RDB$RELATION_NAME'], []);
      fieldNames.get(r['RDB$RELATION_NAME'])[r['RDB$FIELD_ID']] = r['RDB$FIELD_NAME'];
    }
    const formats = new Map();
    for (const r of records(8, sys(8))) {
      const d = readBlob(r['RDB$DESCRIPTOR'].blob);
      const v = new DataView(d.buffer, d.byteOffset, d.byteLength);
      const count = v.getUint16(0, true), fmt = [];
      for (let k = 0; k < count; k++) {
        const o = 2 + k * 12;
        fmt.push({ dtype: d[o], scale: v.getInt8(o + 1), length: v.getUint16(o + 2, true), subType: v.getInt16(o + 4, true), offset: v.getUint32(o + 8, true) });
      }
      formats.set(`${r["RDB$RELATION_ID"]}:${r["RDB$FORMAT"]}`, fmt);
    }

    function table(name) {
      const id = relIds.get(name);
      if (id == null) throw new FormatError(`La tabella ${name} non c'è: il file non sembra una libreria SISTEMA.`);
      const names = fieldNames.get(name) || [];
      return [...records(id, n => {
        const f = formats.get(`${id}:${n}`);
        return f && f.map((d, i) => d.dtype ? { ...d, name: names[i] } : null);
      })];
    }
    return { pageSize, tables: [...relIds.keys()], table };
  }

  // ---- conversione nel formato dell'archivio articoli (stesse regole di tools/slb2json.py) ----
  const NOTA = "Importato da libreria SISTEMA: confrontare con la documentazione del costruttore prima dell'uso.";
  const pulisci = s => String(s || '').replace(/•/g, '*').replace(/\s+/g, ' ').trim();
  const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 20) || 'sistema';

  function converti(meta, componenti, elementi) {
    const produttore = pulisci(meta.AUTHOR);
    const lib = `${produttore}, libreria SISTEMA "${pulisci(meta.NAME)}" versione ${pulisci(meta.LIBVERSION)}`;
    const data = meta.LASTCHANGE instanceof Date ? meta.LASTCHANGE.toISOString().slice(0, 10) : String(meta.LASTCHANGE || '').slice(0, 10);
    const pref = slug(produttore.split(' ')[0]);
    const articoli = [], scartati = [];
    const base = r => {
      const nome = pulisci(r.NAME);
      return { id: `${pref}-${String(r.OID).replace(/[{}]/g, '').toLowerCase()}`, codice: pulisci(r.PARTNO || r.DEVICEGROUP) || nome,
        descrizione: nome, produttore, pfh: null, b10d: null, mttfd: null, plMax: null, dataFonte: data, verificato: false, note: NOTA,
        libreria: `${pulisci(meta.NAME)} ${pulisci(meta.LIBVERSION)}`, gruppo: pulisci(r.DEVICEGROUP) };
    };
    for (const r of componenti) {
      if (!(r.PFH > 0)) { scartati.push(['sottosistema senza PFH', pulisci(r.NAME)]); continue; }
      const a = base(r);
      a.tipo = String(r.DEVICEGROUP || '').startsWith('CS') ? 'logica' : 'sensore';
      a.pfh = Math.round(r.PFH * 1e9 * 1e6) / 1e6; // 1/h → 10⁻⁹/h
      a.fonte = `${lib}, sottosistema "${a.descrizione}" (cat. ${String(r.CAT || '').trim().replace('cat', '')}, mission time ${r.MISSIONTIME} anni)`;
      articoli.push(a);
    }
    for (const r of elementi) {
      const a = base(r);
      a.tipo = 'sensore';
      if (r.MTTFDDET === 'detB10D' && r.B10D > 0) a.b10d = r.B10D;
      else if (r.MTTFDDET === 'detDirect' && r.MTTFD > 0) a.mttfd = r.MTTFD;
      else { scartati.push([`elemento con determinazione ${r.MTTFDDET}`, a.descrizione]); continue; }
      a.fonte = `${lib}, elemento "${a.descrizione}"`;
      articoli.push(a);
    }
    return { articoli, scartati };
  }

  // Legge un file .slb e restituisce { libreria, articoli, scartati }
  function importa(bytes) {
    const db = open(bytes);
    const meta = db.table('LIBMETADATA')[0];
    const join = (rows, devs) => { const m = new Map(devs.map(d => [d.OID, d])); return rows.map(r => ({ ...m.get(r.METADEVICEOID), ...r })); };
    const devC = db.table('METADEVICECOMPONENTS'), devE = db.table('METADEVICEELEMENTS');
    const comp = join(db.table('COMPONENTOPS').filter(r => r.SFOPOID == null), devC);
    const elem = join(db.table('ELEMENTOPS').filter(r => r.PARENTOPOID == null), devE);
    return { libreria: `${pulisci(meta.AUTHOR)} · ${pulisci(meta.NAME)} ${pulisci(meta.LIBVERSION)}`, ...converti(meta, comp, elem) };
  }

  return { open, decompress, converti, importa, FormatError };
});
