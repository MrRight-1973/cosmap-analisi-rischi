"""Dati iniziali per la dichiarazione, ripresi dalla dichiarazione CE della commessa 25-20."""

from django.db import migrations


def carica(apps, schema_editor):
    Fabbricante = apps.get_model("rischi", "Fabbricante")
    LegislazioneUE = apps.get_model("rischi", "LegislazioneUE")
    if not Fabbricante.objects.exists():
        Fabbricante.objects.create(
            ragione_sociale="C.O.S.M.A.P. s.r.l.",
            indirizzo="Via L. Einaudi, 5 – 35030 Saccolongo (PD) – Italia",
            partita_iva="01678580281",
            luogo="Saccolongo",
            persona_fascicolo="Daniele Carraro",
            indirizzo_persona_fascicolo="c/o C.O.S.M.A.P. s.r.l., Via L. Einaudi, 5 – 35030 Saccolongo (PD) – Italia",
            firmatario="Daniele Carraro",
            qualifica_firmatario="Presidente",
        )
    for codice, titolo, titolo_en in (
        ("2014/30/UE", "Direttiva compatibilità elettromagnetica", "Electromagnetic Compatibility Directive"),
        (
            "2011/65/UE",
            "Direttiva RoHS sulla restrizione dell'uso di determinate sostanze pericolose nelle apparecchiature elettriche ed elettroniche",
            "RoHS Directive on the restriction of the use of certain hazardous substances in electrical and electronic equipment",
        ),
    ):
        LegislazioneUE.objects.get_or_create(
            codice=codice, defaults={"titolo": titolo, "titolo_en": titolo_en, "predefinita": True}
        )


class Migration(migrations.Migration):
    dependencies = [("rischi", "0002_dati_dichiarazione")]
    operations = [migrations.RunPython(carica, migrations.RunPython.noop)]
