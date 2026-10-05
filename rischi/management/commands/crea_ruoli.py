from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from rischi.servizi import RUOLI


class Command(BaseCommand):
    help = "Crea i gruppi Compilatore, Verificatore e Approvatore."

    def handle(self, *args, **opzioni):
        for ruolo in RUOLI:
            _, creato = Group.objects.get_or_create(name=ruolo)
            self.stdout.write(f"{ruolo}: {'creato' if creato else 'già presente'}")
