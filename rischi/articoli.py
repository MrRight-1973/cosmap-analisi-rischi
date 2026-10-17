"""Archivio articoli di sicurezza: import del JSON della safety evaluation (data/archivio-articoli.json).

Stesse regole di archivio.js: stesso id = stesso articolo; se un valore (PFH, B10d, MTTFd) cambia l'articolo torna
"da verificare"; le note già scritte restano. Gli articoli nuovi entrano come sono nel file: quelli importati dalle
librerie dei costruttori sono già "da verificare"."""

import datetime
from dataclasses import dataclass

from django.db import transaction

from .models import ArticoloSicurezza

# chiave del JSON -> campo del modello
CAMPI = {
    "codice": "codice",
    "descrizione": "descrizione",
    "produttore": "produttore",
    "tipo": "tipo",
    "pfh": "pfh",
    "b10d": "b10d",
    "mttfd": "mttfd",
    "plMax": "pl_max",
    "fonte": "fonte",
    "dataFonte": "data_fonte",
    "libreria": "libreria",
    "gruppo": "gruppo",
    "note": "note",
}


class ArchivioNonValido(ValueError):
    pass


@dataclass
class EsitoImport:
    nuovi: int = 0
    aggiornati: int = 0
    invariati: int = 0

    def __str__(self):
        return f"{self.nuovi} nuovi, {self.aggiornati} aggiornati, {self.invariati} invariati"


def _numero(valore):
    if valore in (None, ""):
        return None
    return float(valore)


def _data(valore):
    if not valore:
        return None
    return datetime.date.fromisoformat(str(valore)[:10])


def _valori(voce):
    valori = {}
    for chiave, campo in CAMPI.items():
        valore = voce.get(chiave)
        if campo in ArticoloSicurezza.VALORI:
            valori[campo] = _numero(valore)
        else:
            valori[campo] = "" if valore is None else str(valore)
    if valori["tipo"] not in ArticoloSicurezza.Tipo.values:
        valori["tipo"] = ""
    valori["pl_max"] = valori["pl_max"][:1]
    return valori


def _elenco(dati):
    articoli = dati.get("articoli") if isinstance(dati, dict) else dati
    if not isinstance(articoli, list) or any(not isinstance(a, dict) or not a.get("id") for a in articoli):
        raise ArchivioNonValido("Serve un elenco di articoli, ognuno con il suo id.")
    return articoli


@transaction.atomic
def importa(dati):
    """Aggiunge o aggiorna gli articoli del JSON. Restituisce quanti sono nuovi, aggiornati e invariati."""
    esito = EsitoImport()
    for voce in _elenco(dati):
        valori = _valori(voce)
        utilizzato = _data(voce.get("utilizzato"))
        articolo = ArticoloSicurezza.objects.filter(chiave=voce["id"]).first()
        if articolo is None:
            ArticoloSicurezza.objects.create(
                chiave=voce["id"], verificato=bool(voce.get("verificato")), utilizzato=utilizzato, **valori
            )
            esito.nuovi += 1
            continue
        stessi_valori = all(getattr(articolo, c) == valori[c] for c in ArticoloSicurezza.VALORI)
        recente = max(filter(None, [articolo.utilizzato, utilizzato]), default=None)
        if stessi_valori and articolo.fonte == valori["fonte"] and articolo.utilizzato == recente:
            esito.invariati += 1
            continue
        note = articolo.note or valori["note"]
        for campo, valore in valori.items():
            setattr(articolo, campo, valore)
        articolo.note = note
        articolo.utilizzato = recente
        if not stessi_valori:
            articolo.verificato = False
        articolo.save()
        esito.aggiornati += 1
    return esito
