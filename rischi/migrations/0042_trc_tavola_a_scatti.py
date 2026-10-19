"""Il modulo TRC della libreria di Cosmap è la tavola rotante a scatti (macchine TR): la 0034 lo aveva chiamato
"Tavola rotante in continuo" perché nelle librerie con un modulo TAV a parte la tavola a scatti era quello. Si
rinomina solo se nessun altro modulo ha già il nome "Tavola rotante a scatti"; sigla e codici delle schede restano."""

from django.db import migrations

NOME = "Tavola rotante a scatti"
CONDIZIONE = "Base: macchine TR (TR + CNC, CPL, CPDO, CSL, CNCS…)"


def applica(apps, schema_editor):
    Modulo = apps.get_model("rischi", "Modulo")
    if Modulo.objects.filter(nome=NOME).exists():
        return
    Modulo.objects.filter(sigla="TRC", nome="Tavola rotante in continuo").update(nome=NOME, condizione=CONDIZIONE)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0041_funzioni_tipo_tavola_tav")]
    operations = [migrations.RunPython(applica, migrations.RunPython.noop)]
