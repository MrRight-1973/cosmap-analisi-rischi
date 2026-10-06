"""Codici delle schede con il punto RESS: SIGLA-RESS-indice (es. TAV-01 -> TAV-1.3.8.2-1).

L'indice parte da 1 per ogni coppia modulo/RESS e segue l'ordine dei codici precedenti,
come il generatore della libreria. Le copie nelle revisioni in bozza prendono il nuovo codice;
le revisioni approvate o sostituite restano com'erano.
"""

import re

from django.db import migrations


def rinomina(apps, schema_editor):
    Modulo = apps.get_model("rischi", "Modulo")
    SchedaModello = apps.get_model("rischi", "SchedaModello")
    SchedaAnalisi = apps.get_model("rischi", "SchedaAnalisi")
    for modulo in Modulo.objects.exclude(sigla=""):
        vecchio_formato = re.compile(rf"^{re.escape(modulo.sigla)}-(\d+)$")
        schede = [
            s for s in SchedaModello.objects.filter(modulo=modulo).select_related("requisito")
            if vecchio_formato.match(s.codice)
        ]
        schede.sort(key=lambda s: int(vecchio_formato.match(s.codice).group(1)))
        contatori = {}
        for scheda in schede:
            ress = scheda.requisito.codice
            contatori[ress] = contatori.get(ress, 0) + 1
            vecchio, nuovo = scheda.codice, f"{modulo.sigla}-{ress}-{contatori[ress]}"
            SchedaModello.objects.filter(pk=scheda.pk).update(codice=nuovo)
            SchedaAnalisi.objects.filter(codice=vecchio, revisione__stato="BOZZA").update(codice=nuovo)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0010_codici_per_modulo")]

    operations = [
        migrations.AlterModelOptions(
            name="schedamodello",
            options={
                "ordering": ["modulo__ordine", "requisito__ordine", "codice"],
                "verbose_name": "scheda modello",
                "verbose_name_plural": "schede modello",
            },
        ),
        migrations.RunPython(rinomina, migrations.RunPython.noop),
    ]
