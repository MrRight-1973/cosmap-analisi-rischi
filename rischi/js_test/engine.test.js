// Test del motore. Esecuzione: node --test test/engine.test.js
const { test } = require('node:test');
const assert = require('node:assert/strict');
const E = require('../static/rischi/safety/engine.js');
const ARTICOLI = require('./articoli.js');

// Casi di riferimento del calcolatore S120 (calcolo-pl/CLAUDE.md), ricostruiti con l'archivio.
const s120 = (nCU, dmm) => ({ nome: 'S120', metodo: 'pfh', componenti: [
  { articoloId: 's120-cu320-2pn', qty: nCU }, { articoloId: dmm, qty: 3 * nCU }] });
for (const [nome, ss, nano, pl] of [
  ['12 CU in serie, senza SBC', s120(12, 's120-dmm'), 552, 'd'],
  ['12 CU in serie, SBC su tutti gli assi', s120(12, 's120-dmm-sbc'), 840, 'd'],
  ['una funzione per CU (6 assi)', s120(1, 's120-dmm'), 46, 'e'],
  ['2 CU in serie', s120(2, 's120-dmm'), 92, 'e'],
]) test(nome, () => {
  const r = E.evalSubsystem(ss, ARTICOLI, 20);
  assert.equal(r.nano, nano);
  assert.equal(r.pl, pl);
});

test('grafo del rischio', () => {
  assert.equal(E.plr('S1', 'F1', 'P1'), 'a');
  assert.equal(E.plr('S1', 'F2', 'P2'), 'c');
  assert.equal(E.plr('S2', 'F1', 'P1'), 'c');
  assert.equal(E.plr('S2', 'F2', 'P2'), 'e');
  assert.equal(E.plr('S2', null, 'P1'), null);
});

test('B10d → MTTFd e T10d (allegato C)', () => {
  const n = E.nop(220, 16, 60); // 211 200 cicli/anno
  assert.equal(n, 211200);
  assert.ok(Math.abs(E.b10dToMttfd(1e6, n) - 47.35) < 0.01);
  assert.ok(Math.abs(E.t10d(1e6, n) - 4.735) < 0.001);
});

test('livelli MTTFd e DC', () => {
  assert.deepEqual([2, 3, 10, 30, 100].map(E.mttfdLevel), ['insufficiente', 'basso', 'medio', 'alto', 'alto']);
  assert.deepEqual([0, 60, 90, 99].map(E.dcLevel), ['nessuno', 'basso', 'medio', 'alto']);
});

test('simmetrizzazione di due canali uguali restituisce lo stesso valore', () => {
  assert.ok(Math.abs(E.symmetrize(50, 50) - 50) < 1e-9);
});

test('CCF: tutte le misure fanno 100 punti', () => {
  assert.equal(E.ccfScore(Object.fromEntries(E.CCF_MEASURES.map(m => [m.id, true]))), 100);
});

// Articoli di prova con valori fittizi: servono solo a esercitare la logica.
const PROVA = [
  { id: 'fungo', codice: 'FUNGO-PROVA', b10d: 100000, fonte: 'test' },
  { id: 'cpu', codice: 'CPU-PROVA', pfh: 5, fonte: 'test' },
  { id: 'pann', codice: 'PANN-PROVA', pfh: 40, fonte: 'test' },
];
const cat3 = (extra) => ({ nome: 'Fungo', metodo: 'arch', categoria: '3', percorso: 'Fungo',
  componenti: [
    { articoloId: 'fungo', canale: 1, dc: 99, dop: 220, hop: 16, tcycle: 3600 },
    { articoloId: 'fungo', canale: 2, dc: 99, dop: 220, hop: 16, tcycle: 3600 }],
  ccf: { separazione: true, diversita: true, emc: true, ambiente: true }, ...extra });

test('architettura designata: MTTFd capped a 100 anni, DCavg, CCF', () => {
  const r = E.evalSubsystem(cat3({ pfhK1: 50 }), PROVA, 20);
  assert.equal(r.mttfd, 100);
  assert.equal(r.mttfdLevel, 'alto');
  assert.equal(r.dcavg, 99);
  assert.equal(r.ccf, 70);
  assert.deepEqual(r.errors, []);
  assert.equal(r.pl, 'e');
});

test('architettura designata senza categoria: niente PFH da tab. K.1, PL non determinato', () => {
  const r = E.evalSubsystem(cat3({ categoria: null }), PROVA, 20);
  assert.equal(r.pl, null);
  assert.ok(r.warns.some(w => w.includes('PFH non disponibile')));
});

test('categoria 3 con CCF insufficiente è un errore', () => {
  const r = E.evalSubsystem(cat3({ ccf: { emc: true }, pfhK1: 50 }), PROVA, 20);
  assert.ok(r.errors.some(e => e.includes('CCF')));
});

test('funzione: percorsi alternativi, vale il peggiore, confronto con PLr', () => {
  const fn = { nome: 'Emergenza', S: 'S2', F: 'F1', P: 'P2', sottosistemi: [
    cat3({ pfhK1: 50, ruolo: 'rilevamento' }),
    { nome: 'Pannello', ruolo: 'rilevamento', metodo: 'pfh', percorso: 'Pannello', componenti: [{ articoloId: 'pann' }] },
    { nome: 'F-CPU', ruolo: 'logica', metodo: 'pfh', componenti: [{ articoloId: 'cpu' }] },
    { nome: 'Azionamenti', ruolo: 'attuazione', metodo: 'pfh', componenti: [{ articoloId: 's120-cu320-2pn', qty: 12 }, { articoloId: 's120-dmm', qty: 36 }] },
  ] };
  const r = E.evalFunction(fn, [...PROVA, ...ARTICOLI], 20);
  assert.equal(r.plr, 'd');
  assert.deepEqual(r.paths.map(p => [p.nome, p.nano]), [['Fungo', 607], ['Pannello', 597]]);
  assert.equal(r.worst.nome, 'Fungo');
  assert.equal(r.pl, 'd');
  assert.equal(r.ok, true);
});

test('funzione senza rilevamento e logica non è soddisfatta', () => {
  const r = E.evalFunction({ S: 'S1', F: 'F1', P: 'P1', sottosistemi: [
    { nome: 'Azionamenti', ruolo: 'attuazione', metodo: 'pfh', componenti: [{ articoloId: 's120-cu320-2pn' }] }] }, ARTICOLI, 20);
  assert.equal(r.pl, 'e');
  assert.equal(r.ok, false);
});

test('categoria B con due canali: PL limitato e avvisi', () => {
  const ss = { nome: 'Rilevamento', metodo: 'arch', categoria: 'B', pfhK1: 42.9, componenti: [
    { articoloId: 'fungo', canale: 1, dc: 99, dop: 220, hop: 16, tcycle: 45 },
    { articoloId: 'fungo', canale: 2, dc: 99, dop: 220, hop: 16, tcycle: 45 }] };
  const r = E.evalSubsystem(ss, PROVA, 20);
  assert.equal(r.pl, 'b');
  assert.ok(r.warns.some(w => w.includes('PL limitato a b dalla categoria B (dal PFH sarebbe e)')));
  assert.ok(r.warns.some(w => w.includes('un solo canale')));
  const r3 = E.evalSubsystem({ ...ss, categoria: '3' }, PROVA, 20);
  assert.equal(r3.pl, 'e');
  assert.ok(!r3.warns.some(w => w.includes('limitato') || w.includes('un solo canale')));
});

// Colonna PL della tab. K.1 (stessa fonte), riga per riga: controlla la trascrizione dei valori PFH.
const K1_PL = {
  B: 'a'.repeat(15) + 'b'.repeat(9),
  1: 'bbb' + 'c'.repeat(11),
  '2/basso': 'a'.repeat(10) + 'b'.repeat(11) + 'c'.repeat(11) + 'd'.repeat(6),
  '2/medio': 'a'.repeat(7) + 'b'.repeat(11) + 'c'.repeat(8) + 'd'.repeat(12),
  '3/basso': 'a'.repeat(3) + 'b'.repeat(11) + 'c'.repeat(8) + 'd'.repeat(16),
  '3/medio': 'b'.repeat(7) + 'c'.repeat(9) + 'd'.repeat(16) + 'e'.repeat(6),
  '4/alto': 'e'.repeat(14),
};
test('tab. K.1: ogni PFH dà il PL della tabella e decresce con MTTFd', () => {
  E.K1_COLONNE.forEach((col, j) => {
    const valori = E.K1_RIGHE.map(r => r[j]).filter(v => v != null).map(Number);
    assert.equal(valori.map(v => E.toPL(v).pl).join(''), K1_PL[col], col);
    for (let i = 1; i < valori.length; i++) assert.ok(valori[i] < valori[i - 1], `${col} riga ${i}`);
  });
  assert.equal(E.K1_RIGHE.length, E.K1_MTTFD.length);
});

test('tab. K.1: riga inferiore, colonne e casi limite', () => {
  assert.equal(E.pfhK1('3', 'medio', 100).nano, 42.9);
  assert.equal(E.pfhK1('3', 'medio', 99).riga, 91);          // riga immediatamente inferiore
  assert.equal(E.pfhK1('3', 'alto', 100).nano, 42.9);         // DC alta in cat. 3 → colonna DC media
  assert.equal(E.pfhK1('4', 'alto', 1420).nano, 24.7);        // oltre 100 anni → riga 100
  assert.equal(E.pfhK1('2', 'basso', 10).nano, 7180);
  assert.equal(E.pfhK1('B', 'nessuno', 12.5).nano, 9510);
  assert.ok(E.pfhK1('1', 'nessuno', 20).errore);             // cat. 1 solo da 30 anni
  assert.ok(E.pfhK1('4', 'medio', 100).errore);
  assert.ok(E.pfhK1('3', 'nessuno', 100).errore);
  assert.ok(E.pfhK1('3', 'medio', 2.5).errore);
});

test('architettura designata: PFH dalla tab. K.1 se non inserito a mano', () => {
  const r = E.evalSubsystem(cat3({}), PROVA, 20); // MTTFd 100 anni, DCavg 99 % (alta → colonna DC media)
  const ss = cat3({});
  assert.equal(r.nano, 42.9);
  assert.equal(r.pl, 'e');
  assert.equal(r.k1.riga, 100);
  const m = E.evalSubsystem({ ...ss, pfhK1: 60 }, PROVA, 20);
  assert.equal(m.nano, 60);
  assert.ok(m.warns.some(w => w.includes('diverso dalla tab. K.1')));
});
