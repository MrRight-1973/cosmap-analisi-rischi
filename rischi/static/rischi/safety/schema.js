// Schema a blocchi di una funzione di sicurezza: percorsi alternativi (righe) e sottosistemi in serie.
// Un sottosistema con percorso vuoto è comune a tutti i percorsi. Funzioni pure sul modello della
// funzione ({ sottosistemi, percorsi }); nel browser window.Schema, in Node module.exports.
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Schema = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const ORDINE = ['rilevamento', 'comunicazione', 'logica', 'attuazione'];
  const nomeDi = ss => (ss.percorso || '').trim();

  // Nomi dei percorsi, nell'ordine in cui sono stati creati; [''] = percorso unico
  function percorsi(f) {
    const nomi = [...new Set([...(f.percorsi || []), ...f.sottosistemi.map(nomeDi)].filter(Boolean))];
    return nomi.length ? nomi : [''];
  }

  // Sottosistemi in serie lungo un percorso: i suoi più quelli comuni, in ordine di ruolo
  function catena(f, nome) {
    const rank = ss => { const i = ORDINE.indexOf(ss.ruolo); return i < 0 ? ORDINE.length : i; };
    return f.sottosistemi
      .map((ss, i) => ({ ss, i }))
      .filter(({ ss }) => !nomeDi(ss) || nomeDi(ss) === nome)
      // stesso ruolo: prima i blocchi del percorso (es. scheda F-DI), poi quelli comuni (es. F-CPU)
      .sort((a, b) => rank(a.ss) - rank(b.ss) || !nomeDi(a.ss) - !nomeDi(b.ss) || a.i - b.i)
      .map(x => x.ss);
  }

  // Aggiunge un percorso alternativo e ne restituisce il nome. Passando da uno a due percorsi,
  // gli iniziatori già presenti (rilevamento comune) vanno nel primo: il resto resta comune.
  function aggiungiPercorso(f) {
    const nomi = percorsi(f).filter(Boolean);
    const libero = () => { let n = 1; while (nomi.includes(`Percorso ${n}`)) n++; return `Percorso ${n}`; };
    if (!nomi.length) {
      const primo = libero();
      nomi.push(primo);
      for (const ss of f.sottosistemi) if (ss.ruolo === 'rilevamento' && !nomeDi(ss)) ss.percorso = primo;
    }
    const nuovo = libero();
    nomi.push(nuovo);
    f.percorsi = nomi;
    return nuovo;
  }

  function rinominaPercorso(f, vecchio, nuovo) {
    nuovo = (nuovo || '').trim();
    const elenco = percorsi(f).filter(Boolean);
    if (!nuovo || !elenco.includes(vecchio) || elenco.includes(nuovo)) return false;
    for (const ss of f.sottosistemi) if (nomeDi(ss) === vecchio) ss.percorso = nuovo;
    f.percorsi = elenco.map(n => (n === vecchio ? nuovo : n));
    return true;
  }

  // Elimina il percorso e i sottosistemi solo suoi; quelli comuni restano
  function eliminaPercorso(f, nome) {
    f.sottosistemi = f.sottosistemi.filter(ss => nomeDi(ss) !== nome);
    f.percorsi = percorsi(f).filter(n => n && n !== nome);
  }

  // Schema con confluenza: se in ogni percorso i blocchi comuni stanno tutti in coda, ciascun percorso
  // si disegna con i soli blocchi propri e confluisce nei comuni, disegnati una volta sola.
  // Restituisce { propri: Map(nome → blocchi), comuni } oppure null se il disegno a confluenza non si applica.
  function confluenza(f) {
    const nomi = percorsi(f).filter(Boolean);
    if (nomi.length < 2) return null;
    const comuni = catena(f, nomi[0]).filter(ss => !nomeDi(ss));
    if (!comuni.length) return null;
    const propri = new Map();
    for (const nome of nomi) {
      const c = catena(f, nome);
      const i = c.findIndex(ss => !nomeDi(ss));
      if (c.slice(i).some(ss => nomeDi(ss))) return null; // un blocco proprio dopo un comune: serve la catena intera
      propri.set(nome, c.slice(0, i));
    }
    return { propri, comuni };
  }

  // Sottosistemi raggruppati come nello schema: un gruppo per percorso (blocchi propri in ordine di catena),
  // poi i blocchi comuni. Con un solo percorso, un gruppo unico in ordine di catena.
  function gruppi(f) {
    const nomi = percorsi(f).filter(Boolean);
    if (!nomi.length) return [{ titolo: '', comune: false, blocchi: catena(f, '') }];
    const out = nomi.map(nome => ({ titolo: nome, comune: false, blocchi: catena(f, nome).filter(ss => nomeDi(ss) === nome) }));
    const comuni = catena(f, nomi[0]).filter(ss => !nomeDi(ss));
    if (comuni.length) out.push({ titolo: 'Comuni a tutti i percorsi', comune: true, blocchi: comuni });
    // blocchi con un percorso non più in elenco (non dovrebbe accadere): in fondo, per non perderli
    const visti = new Set(out.flatMap(g => g.blocchi));
    const altri = f.sottosistemi.filter(ss => !visti.has(ss));
    if (altri.length) out.push({ titolo: 'Altri', comune: false, blocchi: altri });
    return out;
  }

  return { ORDINE, percorsi, catena, confluenza, gruppi, aggiungiPercorso, rinominaPercorso, eliminaPercorso };
});
