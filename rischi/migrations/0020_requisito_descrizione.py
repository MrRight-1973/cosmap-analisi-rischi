from django.db import migrations, models


def riordina(apps, schema_editor):
    from rischi.models import ordine_codice

    RequisitoRESS = apps.get_model("rischi", "RequisitoRESS")
    for requisito in RequisitoRESS.objects.all():
        requisito.ordine = ordine_codice(requisito.codice)
        requisito.save(update_fields=["ordine"])


class Migration(migrations.Migration):
    dependencies = [("rischi", "0019_logo_fabbricante")]

    operations = [
        migrations.RenameField("requisitoress", "novita", "descrizione"),
        migrations.AlterField(
            model_name="requisitoress",
            name="descrizione",
            field=models.TextField(blank=True, help_text="Testo del requisito nell'Allegato III del Regolamento."),
        ),
        migrations.RemoveField("requisitoress", "azione"),
        migrations.RemoveField("requisitoress", "nuovo"),
        migrations.RemoveField("requisitoress", "codice_direttiva"),
        migrations.AlterField(
            model_name="requisitoress",
            name="ordine",
            field=models.PositiveIntegerField(default=0, editable=False),
        ),
        migrations.RunPython(riordina, migrations.RunPython.noop),
    ]
