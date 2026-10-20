// Schema a blocchi di una funzione di sicurezza: percorsi alternativi (righe) e sottosistemi in serie.
// Un sottosistema con percorso vuoto è comune: a tutti i percorsi, oppure solo a quelli elencati in
// "percorsi" (es. modulo F-DI comune ai soli ingressi cablati, mentre quelli PROFIsafe entrano direttamente
// nella F-CPU). Funzioni pure sul modello della funzione ({ sottosistemi, percorsi }); nel browser
// window.Schema, in Node module.exports.
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Schema = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const ORDINE = ['rilevamento', 'comunicazione', 'logica', 'attuazione'];
  const nomeDi = ss => (ss.percorso || '').trim();
  // Percorsi a cui è comune un blocco comune ([] = tutti)
  const soloA = ss => (nomeDi(ss) ? [] : (ss.percorsi || []).map(n => (n || '').trim()).filter(Boolean));

  // Il blocco sta nel percorso? Proprio del percorso, comune a tutti o comune anche a lui.
  function appartiene(ss, nome) {
    if (nomeDi(ss)) return nomeDi(ss) === nome;
    const elenco = soloA(ss);
    return !elenco.length || !nome || elenco.includes(nome);
  }

  // Nomi dei percorsi, nell'ordine in cui sono stati creati; [''] = percorso unico
  function percorsi(f) {
    const nomi = [...new Set([...(f.percorsi || []), ...f.sottosistemi.map(nomeDi)].filter(Boolean))];
    return nomi.length ? nomi : [''];
  }

  const livello = ss => (nomeDi(ss) ? 0 : soloA(ss).length ? 1 : 2);

  // Sottosistemi in serie lungo un percorso: i suoi più quelli comuni, in ordine di ruolo
  function catena(f, nome) {
    const rank = ss => { const i = ORDINE.indexOf(ss.ruolo); return i < 0 ? ORDINE.length : i; };
    return f.sottosistemi
      .map((ss, i) => ({ ss, i }))
      .filter(({ ss }) => appartiene(ss, nome))
      // stesso ruolo: prima i blocchi del percorso (es. scheda F-DI), poi quelli comuni ad alcuni percorsi,
      // poi quelli comuni a tutti (es. F-CPU)
      .sort((a, b) => rank(a.ss) - rank(b.ss) || livello(a.ss) - livello(b.ss) || a.i - b.i)
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
    for (const ss of f.sottosistemi) {
      if (nomeDi(ss) === vecchio) ss.percorso = nuovo;
      if (soloA(ss).includes(vecchio)) ss.percorsi = soloA(ss).map(n => (n === vecchio ? nuovo : n));
    }
    f.percorsi = elenco.map(n => (n === vecchio ? nuovo : n));
    return true;
  }

  // Elimina il percorso e i sottosistemi solo suoi; quelli comuni restano (un comune ai soli percorsi
  // eliminati sparisce con loro)
  function eliminaPercorso(f, nome) {
    f.sottosistemi = f.sottosistemi.filter(ss => {
      if (nomeDi(ss)) return nomeDi(ss) !== nome;
      const elenco = soloA(ss);
      if (!elenco.includes(nome)) return true;
      ss.percorsi = elenco.filter(n => n !== nome);
      return ss.percorsi.length > 0;
    });
    f.percorsi = percorsi(f).filter(n => n && n !== nome);
  }

  // Percorsi in cui passa il blocco, per le caselle della pagina: tutti, il suo o quelli a cui è comune.
  function percorsiDi(f, ss) {
    return percorsi(f).filter(n => n && appartiene(ss, n));
  }

  // Imposta i percorsi in cui passa il blocco: tutti = comune a tutti, uno = proprio, alcuni = comune a quelli.
  function impostaPercorsi(f, ss, scelti) {
    const nomi = percorsi(f).filter(Boolean);
    scelti = nomi.filter(n => scelti.includes(n));
    if (!scelti.length) return false;
    delete ss.percorsi;
    if (scelti.length === nomi.length) ss.percorso = '';
    else if (scelti.length === 1) ss.percorso = scelti[0];
    else { ss.percorso = ''; ss.percorsi = scelti; }
    return true;
  }

  // Schema con confluenza: se in ogni percorso i blocchi comuni stanno tutti in coda, ciascun percorso si
  // disegna con i soli blocchi propri e confluisce nei comuni, disegnati una volta sola. Con blocchi comuni solo
  // ad alcuni percorsi le confluenze sono più d'una, una dentro l'altra (albero letto da destra):
  //   nodo = { blocchi: comuni in serie, rami: [nodo | { nome, propri }] }
  // La radice ha i blocchi comuni a tutti (anche nessuno, se i percorsi si uniscono solo più a monte).
  // Restituisce null se il disegno a confluenza non si applica (serve la catena intera di ogni percorso).
  function albero(f) {
    const nomi = percorsi(f).filter(Boolean);
    if (nomi.length < 2) return null;
    const code = new Map();
    for (const nome of nomi) {
      const c = catena(f, nome);
      let i = c.findIndex(ss => !nomeDi(ss));
      if (i < 0) i = c.length;
      if (c.slice(i).some(ss => nomeDi(ss))) return null; // un blocco proprio dopo un comune
      code.set(nome, { propri: c.slice(0, i), comuni: c.slice(i) });
    }
    if (![...code.values()].some(x => x.comuni.length)) return null;
    // nodo per un gruppo di percorsi che hanno in comune gli ultimi `fatti` blocchi
    function nodo(gruppo, fatti) {
      const resto = nome => code.get(nome).comuni.slice(0, code.get(nome).comuni.length - fatti);
      // blocchi comuni a tutto il gruppo, andando da destra
      const blocchi = [];
      for (;;) {
        const ultimi = gruppo.map(n => resto(n)[resto(n).length - 1 - blocchi.length]);
        if (!ultimi[0] || ultimi.some(b => b !== ultimi[0])) break;
        blocchi.unshift(ultimi[0]);
      }
      const passati = fatti + blocchi.length;
      const rami = [];
      const visti = new Map();
      for (const nome of gruppo) {
        const r = code.get(nome).comuni.slice(0, code.get(nome).comuni.length - passati);
        if (!r.length) { rami.push({ nome, propri: code.get(nome).propri }); continue; }
        const ultimo = r[r.length - 1];
        if (!visti.has(ultimo)) { visti.set(ultimo, []); rami.push(visti.get(ultimo)); }
        visti.get(ultimo).push(nome);
      }
      for (let k = 0; k < rami.length; k++) {
        if (!Array.isArray(rami[k])) continue;
        // lo stesso blocco non può stare in due rami diversi (altrimenti non è un albero)
        const sotto = nodo(rami[k], passati);
        if (!sotto) return null;
        rami[k] = sotto;
      }
      return { blocchi, rami };
    }
    const radice = nodo(nomi, 0);
    if (!radice) return null;
    // ogni blocco comune deve comparire una volta sola nel disegno
    const contati = [];
    const conta = n => { contati.push(...(n.blocchi || [])); (n.rami || []).forEach(conta); };
    conta(radice);
    return new Set(contati).size === contati.length ? radice : null;
  }

  // Forma semplice (un solo livello di confluenza): { propri: Map(nome → blocchi), comuni }, oppure null.
  function confluenza(f) {
    const a = albero(f);
    if (!a || !a.blocchi.length || a.rami.some(r => r.rami)) return null;
    return { propri: new Map(a.rami.map(r => [r.nome, r.propri])), comuni: a.blocchi };
  }

  // Sottosistemi raggruppati come nello schema: un gruppo per percorso (blocchi propri in ordine di catena),
  // poi i blocchi comuni. Con un solo percorso, un gruppo unico in ordine di catena.
  function gruppi(f) {
    const nomi = percorsi(f).filter(Boolean);
    if (!nomi.length) return [{ titolo: '', comune: false, blocchi: catena(f, '') }];
    const out = nomi.map(nome => ({ titolo: nome, comune: false, blocchi: catena(f, nome).filter(ss => nomeDi(ss) === nome) }));
    // comuni solo ad alcuni percorsi: un gruppo per ogni insieme di percorsi, nell'ordine della catena
    const parziali = new Map();
    for (const nome of nomi) {
      for (const ss of catena(f, nome)) {
        const elenco = soloA(ss);
        if (!elenco.length) continue;
        const chiave = nomi.filter(n => elenco.includes(n)).join(', ');
        if (!parziali.has(chiave)) parziali.set(chiave, []);
        if (!parziali.get(chiave).includes(ss)) parziali.get(chiave).push(ss);
      }
    }
    for (const [chiave, blocchi] of parziali) out.push({ titolo: `Comuni a ${chiave}`, comune: true, blocchi });
    const comuni = f.sottosistemi.filter(ss => !nomeDi(ss) && !soloA(ss).length);
    if (comuni.length) out.push({ titolo: 'Comuni a tutti i percorsi', comune: true, blocchi: catena(f, '').filter(ss => comuni.includes(ss)) });
    // blocchi con un percorso non più in elenco (non dovrebbe accadere): in fondo, per non perderli
    const visti = new Set(out.flatMap(g => g.blocchi));
    const altri = f.sottosistemi.filter(ss => !visti.has(ss));
    if (altri.length) out.push({ titolo: 'Altri', comune: false, blocchi: altri });
    return out;
  }

  return { ORDINE, percorsi, catena, appartiene, albero, confluenza, gruppi, aggiungiPercorso, rinominaPercorso, eliminaPercorso, percorsiDi, impostaPercorsi };
});
