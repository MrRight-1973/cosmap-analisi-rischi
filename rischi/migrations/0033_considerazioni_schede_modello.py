"""Considerazioni precompilate delle schede modello (rischi/dati/considerazioni_schede.json).

Si scrive solo nei campi vuoti e solo se la scheda ha ancora lo stesso requisito: i testi già scritti a mano restano.
"""

import json
from pathlib import Path

from django.db import migrations

DATI = Path(__file__).resolve().parent.parent / "dati" / "considerazioni_schede.json"


def carica(apps, schema_editor):
    SchedaModello = apps.get_model("rischi", "SchedaModello")
    considerazioni = json.loads(DATI.read_text(encoding="utf-8"))
    for scheda in SchedaModello.objects.filter(codice__in=considerazioni).select_related("requisito"):
        voce = considerazioni[scheda.codice]
        if scheda.requisito.codice != voce["requisito"]:
            continue
        cambiati = [campo for campo, testo in voce["campi"].items() if not getattr(scheda, campo).strip()]
        for campo in cambiati:
            setattr(scheda, campo, voce["campi"][campo])
        if cambiati:
            scheda.save(update_fields=cambiati)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0032_allegati_posizione_e_testo")]
    operations = [migrations.RunPython(carica, migrations.RunPython.noop)]
