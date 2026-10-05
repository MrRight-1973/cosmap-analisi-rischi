"""Completa i soggetti esposti nelle analisi in bozza create prima che esistessero.

Uso:  python manage.py completa_soggetti

Per ogni revisione in bozza, le schede senza soggetti prendono quelli della scheda
della libreria da cui sono nate; poi la macchina riceve le figure usate.
Le revisioni approvate non si toccano.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from rischi import servizi
from rischi.models import Revisione


class Command(BaseCommand):
    help = "Copia i soggetti esposti dalla libreria nelle schede in bozza che non li hanno."

    @transaction.atomic
    def handle(self, *args, **opzioni):
        for revisione in Revisione.objects.filter(stato=Revisione.Stato.BOZZA).select_related("analisi__macchina"):
            completate = 0
            for scheda in revisione.schede.filter(soggetti=None, origine__isnull=False).select_related("origine"):
                soggetti = list(scheda.origine.soggetti.all())
                if soggetti:
                    scheda.soggetti.set(soggetti)
                    completate += 1
            servizi.allinea_figure(revisione.analisi.macchina, revisione)
            self.stdout.write(f"{revisione}: {completate} schede completate")
