from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("rischi", "0004_moduli_della_macchina")]

    operations = [
        migrations.RemoveField(model_name="macchina", name="caratteristiche"),
        migrations.RemoveField(model_name="modulo", name="caratteristiche"),
        migrations.DeleteModel(name="Caratteristica"),
    ]
