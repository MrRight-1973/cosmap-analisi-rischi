from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..testo import in_html as testo_in_html
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


@register.filter
def in_html(testo):
    """Testo formattato di una scheda o di un requisito, in sola lettura."""
    return mark_safe(testo_in_html(testo))


@register.simple_tag
def dati_soluzioni():
    """Tipo e testo proposto di ogni soluzione di protezione, per precompilare le misure (scheda.js)."""
    from django.utils.html import json_script

    from ..models import SoluzioneProtezione

    dati = {str(s.pk): {"tipo": s.tipo, "testo": s.testo or s.nome} for s in SoluzioneProtezione.objects.all()}
    return json_script(dati, "dati-soluzioni")
