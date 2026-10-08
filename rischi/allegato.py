"""Testo ufficiale dei requisiti RESS: Regolamento (UE) 2023/1230, Allegato III, parte 1.

rischi/dati/allegato_III_parte_1.json contiene, per ogni punto, titolo e testo (HTML dell'editor delle schede),
ricavati dal PDF della Gazzetta ufficiale L 165 del 29.6.2023. Il testo introduttivo dei punti che hanno
sottopunti (1.3.8, 1.7.1, 1.7.4) è riportato in corsivo all'inizio di ciascun sottopunto.
"""

import json
from pathlib import Path

FILE = Path(__file__).parent / "dati" / "allegato_III_parte_1.json"
# Punti della libreria che nel Regolamento hanno un altro numero
RINUMERATI = {"1.7.4.3": "1.7.5"}


def punti():
    return json.loads(FILE.read_text(encoding="utf-8"))


def aggiorna_requisiti(modello_requisito, riferimento, ordine=None):
    """Porta titolo e descrizione dei requisiti del riferimento al testo del Regolamento; crea i punti mancanti.

    modello_requisito può essere il modello storico di una migrazione: per questo l'ordine si passa a parte."""
    esistenti = {r.codice: r for r in modello_requisito.objects.filter(riferimento=riferimento)}
    for vecchio, nuovo in RINUMERATI.items():
        if vecchio in esistenti and nuovo not in esistenti:
            requisito = esistenti.pop(vecchio)
            requisito.codice = nuovo
            esistenti[nuovo] = requisito
    for punto in punti():
        requisito = esistenti.get(punto["codice"]) or modello_requisito(riferimento=riferimento, codice=punto["codice"])
        requisito.titolo = punto["titolo"][:200]
        requisito.descrizione = punto["descrizione"]
        if ordine:
            requisito.ordine = ordine(requisito.codice)
        requisito.save()
