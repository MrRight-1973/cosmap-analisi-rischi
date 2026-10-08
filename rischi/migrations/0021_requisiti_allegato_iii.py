from django.db import migrations


def aggiorna(apps, schema_editor):
    from rischi.allegato import aggiorna_requisiti
    from rischi.models import ordine_codice

    RiferimentoNormativo = apps.get_model("rischi", "RiferimentoNormativo")
    RequisitoRESS = apps.get_model("rischi", "RequisitoRESS")
    for riferimento in RiferimentoNormativo.objects.filter(codice__contains="2023/1230"):
        aggiorna_requisiti(RequisitoRESS, riferimento, ordine_codice)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0020_requisito_descrizione")]

    operations = [migrations.RunPython(aggiorna, migrations.RunPython.noop)]
