// Crea archivi .zip per i test
const zlib = require('node:zlib');

// Scrive un .zip minimo (metodo 0 = stored, 8 = deflate). Il CRC non viene controllato dal lettore.
function creaZip(voci) {
  const locali = [], centrali = [];
  let off = 0;
  for (const { nome, dati, deflate } of voci) {
    const n = Buffer.from(nome, 'utf8');
    const d = Buffer.from(dati);
    const c = deflate ? zlib.deflateRawSync(d) : d;
    const loc = Buffer.alloc(30);
    loc.writeUInt32LE(0x04034b50, 0); loc.writeUInt16LE(20, 4); loc.writeUInt16LE(0x800, 6); loc.writeUInt16LE(deflate ? 8 : 0, 8);
    loc.writeUInt32LE(c.length, 18); loc.writeUInt32LE(d.length, 22); loc.writeUInt16LE(n.length, 26);
    const cen = Buffer.alloc(46);
    cen.writeUInt32LE(0x02014b50, 0); cen.writeUInt16LE(20, 4); cen.writeUInt16LE(20, 6); cen.writeUInt16LE(0x800, 8); cen.writeUInt16LE(deflate ? 8 : 0, 10);
    cen.writeUInt32LE(c.length, 20); cen.writeUInt32LE(d.length, 24); cen.writeUInt16LE(n.length, 28); cen.writeUInt32LE(off, 42);
    locali.push(loc, n, c); centrali.push(cen, n);
    off += 30 + n.length + c.length;
  }
  const dir = Buffer.concat(centrali);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0); end.writeUInt16LE(voci.length, 8); end.writeUInt16LE(voci.length, 10);
  end.writeUInt32LE(dir.length, 12); end.writeUInt32LE(off, 16);
  return new Uint8Array(Buffer.concat([...locali, dir, end]));
}
module.exports = { creaZip };
