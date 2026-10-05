from django.db import migrations, models


def moduli_dalle_caratteristiche(apps, schema_editor):
    Modulo = apps.get_model("rischi", "Modulo")
    Macchina = apps.get_model("rischi", "Macchina")
    SchedaAnalisi = apps.get_model("rischi", "SchedaAnalisi")
    for modulo in Modulo.objects.all():
        nomi = [c.nome.lower() for c in modulo.caratteristiche.all()]
        if nomi:
            modulo.condizione = ("Se presente " + ", ".join(nomi))[:200]
            modulo.save(update_fields=["condizione"])
    for macchina in Macchina.objects.all():
        moduli = set(Modulo.objects.filter(sempre_attivo=True).values_list("pk", flat=True))
        moduli |= set(
            Modulo.objects.filter(caratteristiche__in=macchina.caratteristiche.all()).values_list("pk", flat=True)
        )
        moduli |= set(
            SchedaAnalisi.objects.filter(revisione__analisi__macchina=macchina).values_list("modulo_id", flat=True)
        )
        macchina.moduli.set(moduli)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0003_dati_iniziali_dichiarazione")]

    operations = [
        migrations.AddField(
            model_name="modulo",
            name="condizione",
            field=models.CharField(
                blank=True,
                help_text="Indicazione per chi sceglie i moduli della commessa.",
                max_length=200,
                verbose_name="quando serve",
            ),
        ),
        migrations.AlterField(
            model_name="modulo",
            name="sempre_attivo",
            field=models.BooleanField(
                default=False,
                help_text="Già selezionato quando si crea una nuova commessa.",
                verbose_name="proposto sempre",
            ),
        ),
        migrations.AddField(
            model_name="macchina",
            name="moduli",
            field=models.ManyToManyField(
                blank=True,
                help_text="Moduli della libreria attivati per questa macchina.",
                related_name="macchine",
                to="rischi.modulo",
            ),
        ),
        migrations.RunPython(moduli_dalle_caratteristiche, migrations.RunPython.noop),
    ]
