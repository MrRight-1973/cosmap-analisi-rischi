import json

from django.core.management.base import BaseCommand, CommandError

from rischi.articoli import ArchivioNonValido, importa


class Command(BaseCommand):
    help = (
        "Importa l'archivio articoli della safety evaluation (data/archivio-articoli.json) "
        "nella libreria degli articoli di sicurezza."
    )

    def add_arguments(self, parser):
        parser.add_argument("file", help="File JSON dell'archivio articoli.")

    def handle(self, *args, **opzioni):
        try:
            with open(opzioni["file"], encoding="utf-8") as f:
                dati = json.load(f)
        except (OSError, json.JSONDecodeError) as errore:
            raise CommandError(f"Non riesco a leggere {opzioni['file']}: {errore}")
        try:
            esito = importa(dati)
        except (ArchivioNonValido, ValueError) as errore:
            raise CommandError(str(errore))
        self.stdout.write(f"Articoli di sicurezza: {esito}.")
