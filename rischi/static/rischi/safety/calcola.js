// Calcolo del PL lato server: legge da stdin { funzione, articoli, missionTime } e scrive il risultato in JSON.
// Usato da rischi/calcolo.py con lo stesso engine.js della pagina.
'use strict';
const path = require('path');
const E = require(path.join(__dirname, 'engine.js'));

let testo = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', d => { testo += d; });
process.stdin.on('end', () => {
  const { funzione, articoli, missionTime } = JSON.parse(testo);
  const r = E.evalFunction(funzione, articoli, missionTime);
  process.stdout.write(JSON.stringify({
    plr: r.plr,
    pl: r.pl,
    pfh: r.worst && r.worst.complete ? r.worst.nano : null,
    ok: r.ok,
    errori: r.errors,
    avvisi: r.warns,
  }));
});
