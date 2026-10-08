from django import template
from django.utils.html import format_html

from ..testo import semplice as testo_semplice

register = template.Library()

ETICHETTE = {"OK": ("ok", "OK"), "SUGGERITE": ("sugg", "Suggerite"), "RICHIESTE": ("rich", "Richieste")}


@register.simple_tag
def esito(se, cl, valore):
    if valore is None:
        return format_html('<span class="esito vuoto">–</span>')
    classe, testo = ETICHETTE[valore]
    return format_html('<span class="esito {}" title="Se {} · Cl {}">{}</span>', classe, se, cl, testo)


@register.filter
def attive(schede):
    """Numero di schede spuntate in una lista di coppie (scheda, spuntata)."""
    return sum(1 for _, spuntata in schede if spuntata)


@register.filter
def semplice(testo):
    """Testo di una scheda senza formattazione (per le anteprime)."""
    return testo_semplice(testo)
