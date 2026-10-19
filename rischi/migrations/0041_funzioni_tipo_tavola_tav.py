"""Le funzioni tipo della tavola create dalla 0040 sul modulo TRC (tavola in continuo) passano a TAV (tavola rotante
a scatti, macchine TR), dove si propongono alle macchine più comuni. Si spostano solo se sono ancora su TRC."""

from django.db import migrations

NOMI = ("Consenso alla rotazione della tavola", "Arresto su perdita di vuoto delle attrezzature")


def applica(apps, schema_editor):
    Modulo = apps.get_model("rischi", "Modulo")
    FunzioneTipo = apps.get_model("rischi", "FunzioneTipo")
    tav = Modulo.objects.filter(sigla="TAV").first()
    if tav:
        FunzioneTipo.objects.filter(nome__in=NOMI, modulo__sigla="TRC").update(modulo=tav)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0040_funzioni_tipo_cosmap")]
    operations = [migrations.RunPython(applica, migrations.RunPython.noop)]
