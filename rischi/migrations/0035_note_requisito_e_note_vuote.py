"""Schede modello: si stampano le note del requisito su tutte (e sulle nuove) e si svuota "Note e considerazioni
generali". Le schede delle commesse già create non cambiano."""

from django.db import migrations, models


def applica(apps, schema_editor):
    SchedaModello = apps.get_model("rischi", "SchedaModello")
    SchedaModello.objects.update(stampa_note_requisito=True, note="")


class Migration(migrations.Migration):
    dependencies = [("rischi", "0034_nuovi_moduli")]
    operations = [
        migrations.AlterField(
            model_name="schedamodello",
            name="stampa_note_requisito",
            field=models.BooleanField(
                default=True,
                help_text="Nella valutazione dei rischi riporta il testo del requisito RESS (Allegato III del Regolamento).",
                verbose_name="stampa le note del requisito nel PDF",
            ),
        ),
        migrations.AlterField(
            model_name="schedaanalisi",
            name="stampa_note_requisito",
            field=models.BooleanField(
                default=True,
                help_text="Nella valutazione dei rischi riporta il testo del requisito RESS (Allegato III del Regolamento).",
                verbose_name="stampa le note del requisito nel PDF",
            ),
        ),
        migrations.RunPython(applica, migrations.RunPython.noop),
    ]
