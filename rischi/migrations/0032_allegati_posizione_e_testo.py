from django.db import migrations, models


def campi(modello):
    return [
        migrations.RenameField(modello, "didascalia", "testo"),
        migrations.AlterField(
            modello, "testo",
            models.TextField(blank=True, help_text="Testo che accompagna l'immagine nella scheda."),
        ),
        migrations.AddField(
            modello, "allineamento",
            models.CharField(
                "posizione dell'immagine nella pagina", max_length=6, default="CENTRO",
                choices=[("SX", "a sinistra"), ("CENTRO", "al centro"), ("DX", "a destra")],
            ),
        ),
        migrations.AddField(
            modello, "posizione_testo",
            models.CharField(
                "posizione del testo", max_length=5, default="SOTTO",
                choices=[("SOTTO", "sotto l'immagine"), ("SOPRA", "sopra l'immagine"),
                         ("SX", "a sinistra dell'immagine"), ("DX", "a destra dell'immagine")],
            ),
        ),
    ]


class Migration(migrations.Migration):
    dependencies = [("rischi", "0031_allegati_schede")]

    operations = campi("allegatomodello") + campi("allegatoanalisi")
