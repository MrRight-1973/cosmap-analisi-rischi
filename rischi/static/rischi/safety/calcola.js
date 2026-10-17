// Calcolo del PL lato server con lo stesso engine.js della pagina, usato da rischi/calcolo.py.
// Legge da stdin { funzione, articoli, missionTime } e scrive il risultato in JSON; con { funzioni: [{ id, funzione, missionTime }], articoli }
// scrive { risultati: { id: risultato }, sistematiche } per la relazione e la validazione; con { elettriche } le
// verifiche elettriche di un quadro.
'use strict';
const path = require('path');
const E = require(path.join(__dirname, 'engine.js'));
const Schema = require(path.join(__dirname, 'schema.js'));
const V = require(path.join(__dirname, 'validazione.js'));

const numero = v => (v == null || Number.isNaN(v) ? null : v);

function risultato(funzione, articoli, missionTime) {
  const f = { ...funzione, sottosistemi: funzione.sottosistemi || [] };
  const r = E.evalFunction(f, articoli, missionTime);
  return {
    plr: r.plr,
    pl: r.pl,
    pfh: r.worst && r.worst.complete ? r.worst.nano : null,
    ok: r.ok,
    errori: r.errors,
    avvisi: r.warns,
    percorsi: r.paths.map(p => ({ nome: p.nome, pfh: p.complete ? p.nano : null, pl: p.pl, completo: p.complete, peggiore: p === r.worst })),
    // Schema a blocchi: un percorso per riga con i blocchi in serie, come nella pagina
    schema: Schema.percorsi(f).map(nome => ({
      nome, blocchi: Schema.catena(f, nome).map(ss => ({ nome: ss.nome || '', ruolo: ss.ruolo || '', comune: !(ss.percorso || '').trim() })),
    })),
    sottosistemi: Schema.gruppi(f).flatMap(g => g.blocchi).map(ss => {
      const x = r.subs.find(s => s.ss === ss).r;
      return {
        nome: ss.nome || '', ruolo: ss.ruolo || '', percorso: (ss.percorso || '').trim(), metodo: x.metodo, categoria: ss.categoria || '',
        pfh: numero(x.nano), pl: x.pl, mttfd: numero(x.mttfd), mttfdLivello: x.mttfdLevel || null, dcavg: numero(x.dcavg),
        dcLivello: x.dcLevel || null, ccf: x.metodo === 'arch' ? x.ccf : null, fonteK1: x.k1 ? x.k1.fonte : null, pfhManuale: !!x.pfhManuale,
        componenti: (ss.componenti || []).map(c => ({ articoloId: c.articoloId, qty: c.qty ?? 1, canale: c.canale || 1, dc: c.dc ?? null })),
      };
    }),
    prove: V.proveAuto(f),
  };
}

// Verifiche elettriche di un quadro (IEC 60204-1, cap. 18): prove con esito e valore, riepilogo del registro misure
// e, per le righe 18.2.2, 18.2.3 e 18.3 senza valore scritto, il valore peggiore del registro.
function elettriche(el) {
  const prove = V.proveElettriche(el);
  const r = V.riepilogoRegistro(el);
  const dalRegistro = { continuita: r.rpeMax && `max ${r.rpeMax}`, anello: r.zsMax && `max ${r.zsMax}`, isolamento: r.isoMin && `min ${r.isoMin}` };
  return {
    prove: prove.map(p => ({ ...p, extra: undefined, dalRegistro: dalRegistro[p.key] || null })),
    riepilogo: V.riepilogo(prove),
    registro: r,
    isolamento: (el.cavi || []).map(V.esitoIsolamento),
    colonne: { equipotenziali: V.COLONNE_EQUI, cavi: V.COLONNE_CAVI, misure: [...V.MISURE_CAVI, 'note'] },
    fonte: V.FONTE_ELETTRICHE,
    isoMin: V.ISO_MIN,
  };
}

let testo = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => { testo += d; });
process.stdin.on('end', () => {
  const dati = JSON.parse(testo);
  const uscita = dati.elettriche ? elettriche(dati.elettriche) : dati.funzioni
    ? {
      risultati: Object.fromEntries(dati.funzioni.map(x => [x.id, risultato(x.funzione, dati.articoli, x.missionTime || dati.missionTime)])),
      sistematiche: V.MISURE_SISTEMATICHE,
    }
    : risultato(dati.funzione, dati.articoli, dati.missionTime);
  process.stdout.write(JSON.stringify(uscita));
});
