// node --test safety-eval/test/zip.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const { apri, FormatError } = require('../static/rischi/safety/zip.js');

const { creaZip } = require('./crea-zip.js');

test('apri: file stored e deflate, cartelle e nomi UTF-8', async () => {
  const testo = 'ciao '.repeat(1000);
  const files = apri(creaZip([{ nome: 'a.txt', dati: 'abc' }, { nome: 'PNG/più.xml', dati: testo, deflate: true }]));
  assert.deepEqual(files.map(f => [f.nome, f.dimensione]), [['a.txt', 3], ['PNG/più.xml', testo.length]]);
  assert.equal(Buffer.from(await files[0].leggi()).toString(), 'abc');
  assert.equal(Buffer.from(await files[1].leggi()).toString(), testo);
});

test('apri: non è uno zip → FormatError', () => {
  assert.throws(() => apri(new Uint8Array(100)), FormatError);
});
