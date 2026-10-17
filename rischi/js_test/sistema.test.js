// node --test safety-eval/test/sistema.test.js
// Le librerie dei costruttori non stanno nel repository (licenza): qui si prova la logica
// su dati sintetici. Il confronto completo con Firebird si fa in locale con una libreria vera.
const test = require('node:test');
const assert = require('node:assert/strict');
const { decompress, converti, open, FormatError } = require('../static/rischi/safety/sistema.js');

test('decompress: letterali, ripetizioni, contatori lunghi', () => {
  const src = Uint8Array.from([3, 1, 2, 3, 0xfc, 9, 0xff, 0x0a, 0x00, 7]); // 1 2 3, 4×9, -1 → 10×7 (uscita arrotondata a 8 byte)
  assert.deepEqual([...decompress(src, 17)].slice(0, 17), [1, 2, 3, 9, 9, 9, 9, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7]);
  const r = decompress(Uint8Array.from([0xfe, 0x00, 0x01, 0x00, 0x00, 5]), 256); // -2 → 256×5
  assert.equal(r.length, 256);
  assert.ok(r.every(x => x === 5));
});

test('decompress: record troppo corto → FormatError', () => {
  assert.throws(() => decompress(Uint8Array.from([2, 1, 2]), 16), FormatError);
});

test('open rifiuta file che non sono librerie SISTEMA', () => {
  assert.throws(() => open(new Uint8Array(4096)), FormatError);
  assert.throws(() => open(new Uint8Array(10)), FormatError);
});

test('converti: PFH 1/h → 10⁻⁹/h, B10d/MTTFd, scarti, fonte', () => {
  const meta = { NAME: 'Libreria  prova', AUTHOR: 'Pizzato Elettrica s.r.l.', LIBVERSION: '1.0', LASTCHANGE: new Date('2024-05-02T10:00:00Z') };
  const comp = [
    { OID: '{AB-12}', NAME: 'Modulo CS', PFH: 1.23e-9, DEVICEGROUP: 'CS AR', PARTNO: 'CS AR-01', CAT: 'cat4', MISSIONTIME: 20 },
    { OID: '{CD}', NAME: 'Senza PFH', PFH: -2, DEVICEGROUP: 'X', PARTNO: 'X', CAT: 'cat3', MISSIONTIME: 20 },
  ];
  const elem = [
    { OID: '{E1}', NAME: 'Interruttore', B10D: 2e7, MTTFD: null, MTTFDDET: 'detB10D', DEVICEGROUP: 'FR', PARTNO: 'FR 693' },
    { OID: '{E2}', NAME: 'Sensore', B10D: null, MTTFD: 150, MTTFDDET: 'detDirect', DEVICEGROUP: 'ST', PARTNO: '' },
    { OID: '{E3}', NAME: 'Calcolato', B10D: null, MTTFD: 80, MTTFDDET: 'detLambda', DEVICEGROUP: 'X', PARTNO: 'X' },
  ];
  const { articoli, scartati } = converti(meta, comp, elem);
  assert.deepEqual(articoli.map(a => a.id), ['pizzato-ab-12', 'pizzato-e1', 'pizzato-e2']);
  assert.equal(articoli[0].pfh, 1.23);
  assert.equal(articoli[0].tipo, 'logica');
  assert.equal(articoli[0].fonte, 'Pizzato Elettrica s.r.l., libreria SISTEMA "Libreria prova" versione 1.0, sottosistema "Modulo CS" (cat. 4, mission time 20 anni)');
  assert.equal(articoli[1].b10d, 2e7);
  assert.equal(articoli[2].mttfd, 150);
  assert.equal(articoli[2].codice, 'ST');
  assert.ok(articoli.every(a => a.verificato === false && a.dataFonte === '2024-05-02'));
  assert.equal(scartati.length, 2);
});
