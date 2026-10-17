// node --test safety-eval/test/validazione.test.js
const test = require('node:test');
const assert = require('node:assert/strict');
const V = require('../static/rischi/safety/validazione.js');

const ss = (id, ruolo, extra = {}) => ({ id, nome: id, ruolo, percorso: '', metodo: 'pfh', componenti: [], ...extra });

test('prove standard: funzionale, tempo, reset, poi un controllo per blocco', () => {
  const f = { sottosistemi: [ss('Fungo', 'rilevamento', { metodo: 'arch', categoria: '4' }), ss('F-CPU', 'logica'), ss('Drive', 'attuazione', { metodo: 'arch', categoria: '1' })] };
  const keys = V.proveAuto(f).map(p => p.key);
  assert.deepEqual(keys, ['funz:', 'tempo', 'reset', 'guasto:Fungo', 'corto:Fungo', 'param:F-CPU']);
  assert.match(V.proveAuto(f)[0].testo, /\(Fungo\)/);
});

test('una prova funzionale per percorso con i suoi iniziatori; cat. 2 = test periodico', () => {
  const f = { sottosistemi: [ss('Fungo', 'rilevamento', { percorso: 'Quadro' }), ss('Barriera', 'rilevamento', { percorso: 'Zona' }),
    ss('Relè', 'logica', { metodo: 'arch', categoria: '2' })] };
  const p = V.proveAuto(f);
  assert.equal(p[0].key, 'funz:Quadro'); assert.match(p[0].testo, /^Quadro: .*\(Fungo\)/);
  assert.equal(p[1].key, 'funz:Zona'); assert.match(p[1].testo, /\(Barriera\)/);
  assert.match(p.find(x => x.key === 'guasto:Relè').testo, /test periodico/);
});

test('esiti per chiave, prove aggiunte e riepilogo', () => {
  const f = { sottosistemi: [ss('KTP', 'rilevamento')],
    validazione: { esiti: { 'funz:': { esito: 'ok' }, tempo: { esito: 'ok' }, reset: { esito: 'na' }, 'param:KTP': { esito: 'ok' }, 'extra:a': { esito: '' } },
      extra: [{ id: 'a', testo: 'Prova aggiunta', atteso: 'x' }] } };
  const lista = V.prove(f);
  assert.equal(lista.length, 5);
  assert.equal(lista[4].testo, 'Prova aggiunta');
  assert.deepEqual(V.riepilogo(lista), { totali: 5, ok: 3, ko: 0, na: 1, aperte: 1, completa: false });
  f.validazione.esiti['extra:a'].esito = 'ok';
  assert.equal(V.riepilogo(V.prove(f)).completa, true);
  f.validazione.esiti.tempo.esito = 'ko';
  assert.equal(V.riepilogo(V.prove(f)).completa, false);
});

test('nessuna prova senza funzione = non validata', () => {
  assert.equal(V.riepilogo([]).completa, false);
});

test('verifiche elettriche: prove del cap. 18 con clausola, punti aggiunti e valori misurati', () => {
  assert.deepEqual(V.PROVE_ELETTRICHE.map(p => p.clausola), ['18.2.2', '18.2.3', '18.3', '18.4', '18.5', '18.6']);
  const el = { esiti: { isolamento: { misurato: '250', esito: 'ok' }, 'extra:q2': { misurato: '0,08' } },
    extra: [{ id: 'q2', testo: 'Continuità PE motore M2', criterio: 'continuità', unita: 'Ω' }] };
  const lista = V.proveElettriche(el);
  assert.equal(lista.length, 7);
  assert.equal(lista.find(p => p.key === 'isolamento').misurato, '250');
  assert.equal(lista[6].testo, 'Continuità PE motore M2');
  assert.equal(lista[6].misurato, '0,08');
  assert.equal(V.proveElettriche(undefined).length, 6);
});

test('registro misure: lettura dei valori del tecnico, esito isolamento, riepilogo e incolla da foglio di calcolo', () => {
  assert.deepEqual(V.leggiMisura('>1'), { op: '>', v: 1 });
  assert.deepEqual(V.leggiMisura('<0,1'), { op: '<', v: 0.1 });
  assert.deepEqual(V.leggiMisura(' 0,004 '), { op: '', v: 0.004 });
  assert.equal(V.leggiMisura(''), null);
  assert.ok(Number.isNaN(V.leggiMisura('ok').v));
  assert.equal(V.esitoIsolamento({ l1pe: '>1', l2pe: '250' }), 'ok');
  assert.equal(V.esitoIsolamento({ l1pe: '>1', l2pe: '0,8' }), 'ko');
  assert.equal(V.esitoIsolamento({ l1pe: '<1' }), 'ko');
  assert.equal(V.esitoIsolamento({ sigla: 'W1' }), '');
  const el = {
    equipotenziali: [{ punto: 'PE/quadro', rpe: '0,004' }, { punto: 'PE/telaio', rpe: '0,016' }, { punto: 'PE/porta' }],
    cavi: [{ sigla: 'W1', l1pe: '>1', l2pe: '120', rpe: '<0,1', zs: '0,35' }, { sigla: 'W2', l1pe: '0,5', zs: '0,8' }, { sigla: 'W3' }],
  };
  assert.deepEqual(V.riepilogoRegistro(el), { equipotenziali: 3, cavi: 3, rpeMax: '<0,1', zsMax: '0,8', isoMin: '0,5', isoKo: ['W2'], senzaMisure: 2 });
  const righe = V.daTesto('Sigla\tDa/a\tTipo cavo\nW1.M1\tQ1/M1\tFROR\t4x1.5\t1,5\n\nW1.M2;Q1/M2;FROR', V.COLONNE_CAVI);
  assert.deepEqual(righe.map(r => [r.sigla, r.percorso, r.tipo, r.formazione]), [['W1.M1', 'Q1/M1', 'FROR', '4x1.5'], ['W1.M2', 'Q1/M2', 'FROR', '']]);
});
