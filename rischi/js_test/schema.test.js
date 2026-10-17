// node --test safety-eval/test/schema.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const { percorsi, catena, confluenza, gruppi, aggiungiPercorso, rinominaPercorso, eliminaPercorso } = require('../static/rischi/safety/schema.js');
const E = require('../static/rischi/safety/engine.js');

const ss = (nome, ruolo, percorso = '') => ({ id: nome, nome, ruolo, percorso, metodo: 'pfh', componenti: [] });

test('percorso unico quando nessun sottosistema ha un percorso', () => {
  const f = { sottosistemi: [ss('CPU', 'logica'), ss('Fungo', 'rilevamento')] };
  assert.deepEqual(percorsi(f), ['']);
  assert.deepEqual(catena(f, '').map(x => x.nome), ['Fungo', 'CPU']);
});

test('aggiungiPercorso: gli iniziatori esistenti vanno nel primo percorso, il resto resta comune', () => {
  const f = { sottosistemi: [ss('Fungo', 'rilevamento'), ss('CPU', 'logica'), ss('Drive', 'attuazione')] };
  assert.equal(aggiungiPercorso(f), 'Percorso 2');
  assert.deepEqual(percorsi(f), ['Percorso 1', 'Percorso 2']);
  assert.equal(f.sottosistemi[0].percorso, 'Percorso 1');
  assert.equal(f.sottosistemi[1].percorso, '');
  f.sottosistemi.push(ss('KTP', 'rilevamento', 'Percorso 2'));
  assert.deepEqual(catena(f, 'Percorso 2').map(x => x.nome), ['KTP', 'CPU', 'Drive']);
  assert.equal(aggiungiPercorso(f), 'Percorso 3');
});

test('rinomina ed elimina percorso', () => {
  const f = { sottosistemi: [ss('Fungo', 'rilevamento', 'A'), ss('F-DI', 'logica', 'A'), ss('KTP', 'rilevamento', 'B'), ss('CPU', 'logica')], percorsi: ['A', 'B'] };
  assert.equal(rinominaPercorso(f, 'A', 'B'), false, 'nome già usato');
  assert.equal(rinominaPercorso(f, 'A', 'Funghi'), true);
  assert.deepEqual(percorsi(f), ['Funghi', 'B']);
  assert.deepEqual(catena(f, 'Funghi').map(x => x.nome), ['Fungo', 'F-DI', 'CPU']);
  eliminaPercorso(f, 'Funghi');
  assert.deepEqual(f.sottosistemi.map(x => x.nome), ['KTP', 'CPU']);
  assert.deepEqual(percorsi(f), ['B']);
});

test('lo schema e il motore di calcolo vedono gli stessi percorsi', () => {
  const A = [{ id: 'f', codice: 'F', pfh: 10, fonte: 'x' }, { id: 'k', codice: 'K', pfh: 20, fonte: 'x' }, { id: 'c', codice: 'C', pfh: 5, fonte: 'x' }];
  const comp = id => [{ articoloId: id, qty: 1 }];
  const f = { S: 'S2', F: 'F2', P: 'P2', sottosistemi: [
    { ...ss('Fungo', 'rilevamento', 'Funghi'), componenti: comp('f') }, { ...ss('KTP', 'rilevamento', 'KTP'), componenti: comp('k') },
    { ...ss('CPU', 'logica'), componenti: comp('c') }, { ...ss('Drive', 'attuazione'), componenti: comp('c') }] };
  const r = E.evalFunction(f, A, 20);
  for (const nome of percorsi(f)) {
    const p = r.paths.find(x => x.nome === nome);
    assert.deepEqual([...p.sottosistemi].sort(), catena(f, nome).map(x => x.nome).sort());
  }
  assert.equal(r.worst.nome, 'KTP');
});

test('stesso ruolo: prima il blocco del percorso, poi quello comune', () => {
  const f = { sottosistemi: [ss('CPU', 'logica'), ss('F-DI', 'logica', 'A'), ss('Fungo', 'rilevamento', 'A')] };
  assert.deepEqual(catena(f, 'A').map(x => x.nome), ['Fungo', 'F-DI', 'CPU']);
});

test('confluenza: percorsi con blocchi propri che confluiscono nei comuni', () => {
  const f = { sottosistemi: [ss('Drive', 'attuazione'), ss('Fungo', 'rilevamento', 'Funghi'), ss('CPU', 'logica'),
    ss('F-DI', 'logica', 'Funghi'), ss('KTP', 'rilevamento', 'KTP')], percorsi: ['Funghi', 'KTP'] };
  const c = confluenza(f);
  assert.deepEqual(c.propri.get('Funghi').map(x => x.nome), ['Fungo', 'F-DI']);
  assert.deepEqual(c.propri.get('KTP').map(x => x.nome), ['KTP']);
  assert.deepEqual(c.comuni.map(x => x.nome), ['CPU', 'Drive']);
  assert.deepEqual(gruppi(f).map(g => [g.titolo, g.blocchi.map(x => x.nome)]),
    [['Funghi', ['Fungo', 'F-DI']], ['KTP', ['KTP']], ['Comuni a tutti i percorsi', ['CPU', 'Drive']]]);
});

test('confluenza non applicabile: percorso unico, nessun comune, proprio dopo un comune', () => {
  assert.equal(confluenza({ sottosistemi: [ss('Fungo', 'rilevamento'), ss('CPU', 'logica')] }), null);
  assert.equal(confluenza({ sottosistemi: [ss('A', 'rilevamento', 'A'), ss('B', 'rilevamento', 'B')] }), null);
  // comune di rilevamento prima di una logica propria
  assert.equal(confluenza({ sottosistemi: [ss('Fungo', 'rilevamento'), ss('CPU A', 'logica', 'A'), ss('KTP', 'rilevamento', 'B')] }), null);
  assert.deepEqual(gruppi({ sottosistemi: [ss('CPU', 'logica'), ss('Fungo', 'rilevamento')] }).map(g => g.blocchi.map(x => x.nome)), [['Fungo', 'CPU']]);
});
