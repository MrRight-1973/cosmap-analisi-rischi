from django.db import migrations


def crea(apps, schema_editor):
    from rischi.funzioni_tipo_cosmap import crea as crea_funzioni

    crea_funzioni(apps.get_model("rischi", "FunzioneTipo"), apps.get_model("rischi", "Modulo"))


class Migration(migrations.Migration):
    dependencies = [("rischi", "0039_funzioni_tipo")]

    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
