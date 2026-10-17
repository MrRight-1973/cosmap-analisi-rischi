// Lettore minimo di archivi .zip (metodi "stored" e "deflate"), per i pacchetti dei costruttori
// con database e immagini. Usa DecompressionStream del browser (e di Node ≥ 18): nessuna dipendenza.
// Nel browser espone window.Zip, in Node module.exports.
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Zip = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  class FormatError extends Error {}

  async function inflate(data) {
    const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
    return new Uint8Array(await new Response(stream).arrayBuffer());
  }

  // Restituisce l'elenco dei file: [{ nome, dimensione, leggi() → Promise<Uint8Array> }]
  function apri(bytes) {
    const buf = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    // fine della directory centrale: firma 0x06054b50 negli ultimi 64 KB
    let eocd = -1;
    for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
      if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) throw new FormatError('Il file non è un archivio .zip valido.');
    const count = dv.getUint16(eocd + 10, true);
    let p = dv.getUint32(eocd + 16, true);
    if (p === 0xffffffff || count === 0xffff) throw new FormatError('Archivi .zip a 64 bit non supportati.');
    const utf8 = new TextDecoder('utf-8'), latin = new TextDecoder('latin1');
    const files = [];
    for (let n = 0; n < count; n++) {
      if (dv.getUint32(p, true) !== 0x02014b50) throw new FormatError('Directory dello .zip danneggiata.');
      const flags = dv.getUint16(p + 8, true), metodo = dv.getUint16(p + 10, true);
      const compresso = dv.getUint32(p + 20, true), dimensione = dv.getUint32(p + 24, true);
      const lenNome = dv.getUint16(p + 28, true), lenExtra = dv.getUint16(p + 30, true), lenComm = dv.getUint16(p + 32, true);
      const locale = dv.getUint32(p + 42, true);
      const nome = ((flags & 0x800) ? utf8 : latin).decode(buf.subarray(p + 46, p + 46 + lenNome));
      p += 46 + lenNome + lenExtra + lenComm;
      if (nome.endsWith('/')) continue;
      files.push({
        nome, dimensione,
        async leggi() {
          if (flags & 1) throw new FormatError(`${nome}: file cifrato, non leggibile.`);
          if (dv.getUint32(locale, true) !== 0x04034b50) throw new FormatError(`${nome}: intestazione danneggiata.`);
          const inizio = locale + 30 + dv.getUint16(locale + 26, true) + dv.getUint16(locale + 28, true);
          const dati = buf.subarray(inizio, inizio + compresso);
          if (metodo === 0) return dati;
          if (metodo === 8) return inflate(dati);
          throw new FormatError(`${nome}: compressione ${metodo} non supportata.`);
        },
      });
    }
    return files;
  }

  return { apri, FormatError };
});
