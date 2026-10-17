"""Calcolo del PL di una funzione di sicurezza con il motore della safety evaluation (engine.js, eseguito con Node).

Il browser calcola mentre si compila; al salvataggio il server ricalcola con lo stesso motore, così il PL
registrato nella revisione non dipende da quanto inviato dalla pagina. Senza Node installato il server non
può ricalcolare: la valutazione si salva con i risultati della pagina e lo segnala."""

import json
import shutil
import subprocess
from pathlib import Path

from .models import ArticoloSicurezza

SCRIPT = Path(__file__).resolve().parent / "static" / "rischi" / "safety" / "calcola.js"
MISSION_TIME = 20  # anni, come nella safety evaluation


class CalcoloNonRiuscito(RuntimeError):
    pass


def articoli_della_valutazione(dettaglio):
    """Gli articoli scelti nei sottosistemi, nella forma che usa engine.js (id = chiave dell'archivio)."""
    chiavi = {
        c.get("articoloId")
        for ss in dettaglio.get("sottosistemi", [])
        for c in ss.get("componenti", [])
        if c.get("articoloId")
    }
    return [articolo_js(a) for a in ArticoloSicurezza.objects.filter(chiave__in=chiavi)]


def articolo_js(a):
    return {
        "id": a.chiave, "codice": a.codice, "descrizione": a.descrizione, "produttore": a.produttore,
        "tipo": a.tipo, "pfh": a.pfh, "b10d": a.b10d, "mttfd": a.mttfd, "plMax": a.pl_max or None,
        "fonte": a.fonte, "verificato": a.verificato, "utilizzato": a.utilizzato.isoformat() if a.utilizzato else None,
    }


def node_disponibile():
    return shutil.which("node") is not None


def _esegui(dati):
    nodo = shutil.which("node")
    if not nodo:
        raise CalcoloNonRiuscito("Node non è installato sul server.")
    try:
        uscita = subprocess.run(
            [nodo, str(SCRIPT)], input=json.dumps(dati), capture_output=True, text=True, encoding="utf-8",
            timeout=30, check=True,
        )
        return json.loads(uscita.stdout)
    except (subprocess.SubprocessError, ValueError) as errore:
        raise CalcoloNonRiuscito(f"Calcolo non riuscito: {errore}") from errore


def _funzione_js(funzione, dettaglio):
    return {**dettaglio, "nome": funzione.nome, "S": funzione.s, "F": funzione.f, "P": funzione.p}


def calcola(funzione, dettaglio):
    """Risultato del motore per la funzione: plr, pl, pfh (10⁻⁹/h, percorso peggiore), ok, errori, avvisi, e per la
    relazione percorsi, schema, sottosistemi e prove di validazione ricavate dallo schema."""
    return _esegui({
        "funzione": _funzione_js(funzione, dettaglio),
        "articoli": articoli_della_valutazione(dettaglio),
        "missionTime": dettaglio.get("missionTime") or MISSION_TIME,
    })


def analizza(funzioni):
    """Calcolo di più funzioni in una sola esecuzione di Node (pagina della validazione, relazione).
    Restituisce ({pk funzione: risultato}, misure contro i guasti sistematici di validazione.js)."""
    dettagli = {f.pk: (f.valutazione.dettaglio if hasattr(f, "valutazione") else {}) for f in funzioni}
    articoli = {}
    for dettaglio in dettagli.values():
        for a in articoli_della_valutazione(dettaglio):
            articoli[a["id"]] = a
    uscita = _esegui({
        "funzioni": [
            {"id": f.pk, "funzione": _funzione_js(f, dettagli[f.pk]), "missionTime": dettagli[f.pk].get("missionTime") or MISSION_TIME}
            for f in funzioni
        ],
        "articoli": list(articoli.values()),
    })
    return {int(k): v for k, v in uscita["risultati"].items()}, uscita["sistematiche"]
