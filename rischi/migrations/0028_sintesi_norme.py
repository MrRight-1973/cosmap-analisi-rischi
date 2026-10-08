"""Sintesi di ogni norma nel campo nota: la sintesi va in testa, le note già presenti restano sotto."""

from django.db import migrations

from rischi.dati.sintesi_norme import SINTESI


def carica(apps, schema_editor):
    Norma = apps.get_model("rischi", "Norma")
    for norma in Norma.objects.filter(codice__in=SINTESI):
        sintesi = SINTESI[norma.codice]
        if sintesi in norma.nota:
            continue
        norma.nota = f"{sintesi}\n\n{norma.nota}" if norma.nota.strip() else sintesi
        norma.save(update_fields=["nota"])


class Migration(migrations.Migration):
    dependencies = [("rischi", "0027_regole_norme")]
    operations = [migrations.RunPython(carica, migrations.RunPython.noop)]
