"""Sigle dei moduli e codici delle schede per modulo (es. NL-034 -> TAV-01).

Le schede della libreria NL vengono rinominate modulo per modulo, nell'ordine dei vecchi codici,
come fa il generatore della libreria. Le copie nelle revisioni in bozza prendono il nuovo codice;
le revisioni approvate o sostituite restano com'erano.
"""

from django.db import migrations

SIGLE = {
    "Generale impianto": "GEN",
    "Impianto pasta abrasiva": "PAS",
    "Sistema di comando": "CMD",
    "Cabina di protezione e ripari": "CAB",
    "Tavola rotante – carico/scarico": "TAV",
    "Zona smerigliatura - generale": "ZSM",
    "Zona smerigliatura – generale": "ZSM",
    "Stazione di carico a doppio pallet": "PAL",
    "Gruppo di smerigliatura (robot + smerigliatrici a nastro)": "ROB",
    "Trasportatore a tappeto di scarico": "TRA",
    "Zona pulitura – generale": "ZPU",
    "Unità di lucidatura CNC": "LUC",
    "Equipaggiamento elettrico": "ELE",
    "Equipaggiamento pneumatico": "PNE",
    "Informazioni, marcatura e istruzioni": "INF",
}


def rinomina(apps, schema_editor):
    Modulo = apps.get_model("rischi", "Modulo")
    SchedaModello = apps.get_model("rischi", "SchedaModello")
    SchedaAnalisi = apps.get_model("rischi", "SchedaAnalisi")
    for modulo in Modulo.objects.all():
        sigla = SIGLE.get(modulo.nome)
        if not sigla:
            continue
        if not modulo.sigla:
            modulo.sigla = sigla
            modulo.save(update_fields=["sigla"])
        schede = SchedaModello.objects.filter(modulo=modulo, codice__startswith="NL-").order_by("codice")
        for numero, scheda in enumerate(schede, start=1):
            vecchio, nuovo = scheda.codice, f"{modulo.sigla}-{numero:02d}"
            SchedaModello.objects.filter(pk=scheda.pk).update(codice=nuovo)
            SchedaAnalisi.objects.filter(codice=vecchio, revisione__stato="BOZZA").update(codice=nuovo)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0009_sigla_moduli")]

    operations = [migrations.RunPython(rinomina, migrations.RunPython.noop)]
