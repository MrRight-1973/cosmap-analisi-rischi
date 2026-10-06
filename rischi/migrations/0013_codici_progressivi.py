"""Ritorno ai codici progressivi per modulo (es. TAV-1.3.8.2-1 -> TAV-01).

Le schede della libreria NL riprendono esattamente i codici che avevano prima della migrazione 0011.
Eventuali schede create nel frattempo con il formato SIGLA-RESS-indice prendono il numero successivo
nel loro modulo. Le copie nelle revisioni in bozza seguono la libreria; le schede aggiunte a mano
in bozza prendono il numero successivo libero. Le revisioni approvate o sostituite restano com'erano.
"""

import re

from django.db import migrations, models

CODICI_PRECEDENTI = {
    'GEN-1.1.1-1': 'GEN-01',
    'GEN-1.1.2-1': 'GEN-02',
    'GEN-1.1.3-1': 'GEN-03',
    'GEN-1.1.4-1': 'GEN-04',
    'GEN-1.1.5-1': 'GEN-05',
    'GEN-1.1.6-1': 'GEN-06',
    'GEN-1.1.7-1': 'GEN-07',
    'GEN-1.3.1-1': 'GEN-08',
    'GEN-1.3.4-1': 'GEN-09',
    'GEN-1.3.5-1': 'GEN-10',
    'GEN-1.5.4-1': 'GEN-11',
    'GEN-1.5.8-1': 'GEN-12',
    'GEN-1.5.15-1': 'GEN-13',
    'GEN-1.6.1-1': 'GEN-14',
    'GEN-1.6.2-1': 'GEN-15',
    'GEN-1.6.4-1': 'GEN-16',
    'CMD-1.1.9-1': 'CMD-01',
    'CMD-1.2.1-1': 'CMD-02',
    'CMD-1.2.2-1': 'CMD-03',
    'CMD-1.2.3-1': 'CMD-04',
    'CMD-1.2.4.1-1': 'CMD-05',
    'CMD-1.2.4.2-1': 'CMD-06',
    'CMD-1.2.4.3-1': 'CMD-07',
    'CMD-1.2.4.4-1': 'CMD-08',
    'CMD-1.2.5-1': 'CMD-09',
    'CMD-1.2.6-1': 'CMD-10',
    'CAB-1.3.7-1': 'CAB-01',
    'CAB-1.4.1-1': 'CAB-02',
    'CAB-1.4.2.1-1': 'CAB-03',
    'CAB-1.4.2.2-1': 'CAB-04',
    'CAB-1.4.3-1': 'CAB-05',
    'CAB-1.3.3-1': 'CAB-06',
    'CAB-1.5.14-1': 'CAB-07',
    'TAV-1.3.8.2-1': 'TAV-01',
    'TAV-1.4.3-1': 'TAV-02',
    'TAV-1.1.6-1': 'TAV-03',
    'TAV-1.3.9-1': 'TAV-04',
    'TAV-1.5.5-1': 'TAV-05',
    'ZSM-1.5.13-1': 'ZSM-01',
    'ZSM-1.5.6-1': 'ZSM-02',
    'ZSM-1.5.7-1': 'ZSM-03',
    'ZSM-1.6.5-1': 'ZSM-04',
    'ZSM-1.5.2-1': 'ZSM-05',
    'PAL-1.3.7-1': 'PAL-01',
    'PAL-1.4.3-1': 'PAL-02',
    'PAL-1.1.6-1': 'PAL-03',
    'PAL-1.3.3-1': 'PAL-04',
    'ROB-1.3.8.2-1': 'ROB-01',
    'ROB-1.3.8.1-1': 'ROB-02',
    'ROB-1.3.8.2-2': 'ROB-03',
    'ROB-1.3.2-1': 'ROB-04',
    'ROB-1.3.9-1': 'ROB-05',
    'ROB-1.3.6-1': 'ROB-06',
    'ROB-1.5.5-1': 'ROB-07',
    'ROB-1.6.4-1': 'ROB-08',
    'TRA-1.3.8.1-1': 'TRA-01',
    'TRA-1.3.7-1': 'TRA-02',
    'TRA-1.2.4.3-1': 'TRA-03',
    'TRA-1.5.5-1': 'TRA-04',
    'ZPU-1.5.13-1': 'ZPU-01',
    'ZPU-1.5.6-1': 'ZPU-02',
    'ZPU-1.5.7-1': 'ZPU-03',
    'ZPU-1.6.5-1': 'ZPU-04',
    'LUC-1.3.8.2-1': 'LUC-01',
    'LUC-1.3.8.1-1': 'LUC-02',
    'LUC-1.3.2-1': 'LUC-03',
    'LUC-1.3.9-1': 'LUC-04',
    'LUC-1.6.4-1': 'LUC-05',
    'LUC-1.5.5-1': 'LUC-06',
    'ELE-1.5.1-1': 'ELE-01',
    'ELE-1.5.1-2': 'ELE-02',
    'ELE-1.6.3-1': 'ELE-03',
    'ELE-1.5.6-1': 'ELE-04',
    'PNE-1.5.3-1': 'PNE-01',
    'PNE-1.6.3-1': 'PNE-02',
    'PNE-1.2.6-1': 'PNE-03',
    'PNE-1.5.8-1': 'PNE-04',
    'PAS-1.5.13-1': 'PAS-01',
    'PAS-1.5.3-1': 'PAS-02',
    'PAS-1.6.1-1': 'PAS-03',
    'PAS-1.5.15-1': 'PAS-04',
    'INF-1.7.1.1-1': 'INF-01',
    'INF-1.7.1.2-1': 'INF-02',
    'INF-1.7.2-1': 'INF-03',
    'INF-1.7.3-1': 'INF-04',
    'INF-1.7.4.1-1': 'INF-05',
    'INF-1.7.4.2-1': 'INF-06',
    'INF-1.7.4.3-1': 'INF-07',
}
FORMATO_RESS = re.compile(r"^([A-Z]+)-\d+(?:\.\d+)+-\d+$")


def _successivo(sigla, usati):
    numeri = [int(c.split("-")[1]) for c in usati if re.fullmatch(rf"{re.escape(sigla)}-\d+", c)]
    return f"{sigla}-{max(numeri, default=0) + 1:02d}"


def ripristina(apps, schema_editor):
    SchedaModello = apps.get_model("rischi", "SchedaModello")
    SchedaAnalisi = apps.get_model("rischi", "SchedaAnalisi")
    nuovi = {}
    for scheda in SchedaModello.objects.order_by("pk"):
        if scheda.codice in CODICI_PRECEDENTI:
            nuovi[scheda.pk] = CODICI_PRECEDENTI[scheda.codice]
    usati = set(nuovi.values())
    for scheda in SchedaModello.objects.order_by("pk"):
        trovato = FORMATO_RESS.match(scheda.codice)
        if scheda.pk not in nuovi and trovato:
            nuovi[scheda.pk] = _successivo(trovato.group(1), usati)
            usati.add(nuovi[scheda.pk])
    vecchi = dict(SchedaModello.objects.values_list("pk", "codice"))
    for pk, codice in nuovi.items():
        SchedaModello.objects.filter(pk=pk).update(codice=codice)
        SchedaAnalisi.objects.filter(codice=vecchi[pk], revisione__stato="BOZZA").update(codice=codice)
    for scheda in SchedaAnalisi.objects.filter(revisione__stato="BOZZA").order_by("pk"):
        trovato = FORMATO_RESS.match(scheda.codice)
        if trovato:
            nella_revisione = set(SchedaAnalisi.objects.filter(revisione_id=scheda.revisione_id).values_list("codice", flat=True))
            codice = _successivo(trovato.group(1), usati | nella_revisione)
            SchedaAnalisi.objects.filter(pk=scheda.pk).update(codice=codice)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0012_codice_automatico")]

    operations = [
        migrations.AlterField(
            model_name="schedamodello",
            name="codice",
            field=models.CharField(
                help_text="Si genera da solo: sigla del modulo e numero progressivo (es. TAV-03).",
                max_length=20,
                unique=True,
            ),
        ),
        migrations.RunPython(ripristina, migrations.RunPython.noop),
    ]
