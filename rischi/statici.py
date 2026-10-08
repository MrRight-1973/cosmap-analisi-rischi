"""File statici con la data di modifica nell'indirizzo (es. scheda.js?v=1728370000).

Dopo un aggiornamento il browser scarica subito i CSS e gli script nuovi, senza Ctrl+F5.
"""

import os

from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import StaticFilesStorage


class StaticiAggiornati(StaticFilesStorage):
    def url(self, name):
        indirizzo = super().url(name)
        percorso = finders.find(name) or (self.exists(name) and self.path(name))
        if percorso:
            indirizzo += f"?v={int(os.path.getmtime(percorso))}"
        return indirizzo
