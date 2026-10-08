"""Azione "Duplica" degli elenchi di Libreria e utenti: copia le voci scelte con i loro collegamenti."""

from django.contrib import admin, messages
from django.db import models, transaction
from django.http import HttpResponseRedirect
from django.urls import reverse

from . import models as m


def _valore_libero(modello, campo, valore):
    """Valore non ancora usato per un campo univoco: "valore (copia)", "valore (copia 2)"…"""
    massimo = modello._meta.get_field(campo).max_length or 200
    numero = 1
    while True:
        coda = " (copia)" if numero == 1 else f" (copia {numero})"
        candidato = f"{valore[: massimo - len(coda)]}{coda}"
        if not modello.objects.filter(**{campo: candidato}).exists():
            return candidato
        numero += 1


def _copia_figli(originale, nuovo):
    """Righe che fanno parte della voce: misure della scheda modello, fasce, celle e scale del metodo."""
    if isinstance(originale, m.SchedaModello):
        for misura in originale.misure.all():
            misura.pk = None
            misura.scheda = nuovo
            misura.save()
    elif isinstance(originale, m.MetodoStima):
        fasce = {}
        for fascia in originale.fasce.all():
            vecchia = fascia.pk
            fascia.pk = None
            fascia.metodo = nuovo
            fascia.save()
            fasce[vecchia] = fascia
        for cella in originale.celle.all():
            cella.pk = None
            cella.metodo = nuovo
            cella.fascia = fasce[cella.fascia_id]
            cella.save()
        for scala in originale.scale.all():
            scala.pk = None
            scala.metodo = nuovo
            scala.save()


def copia(originale):
    modello = type(originale)
    collegati = {f.name: list(getattr(originale, f.name).all()) for f in modello._meta.many_to_many}
    nuovo = modello.objects.get(pk=originale.pk)
    nuovo.pk = None
    nuovo._state.adding = True
    for campo in modello._meta.concrete_fields:
        if not campo.unique or campo.primary_key or not isinstance(campo, models.CharField):
            continue
        if isinstance(nuovo, m.SchedaModello) and campo.name == "codice":
            nuovo.codice = ""  # nuovo numero progressivo nel modulo
        else:
            setattr(nuovo, campo.name, _valore_libero(modello, campo.name, getattr(nuovo, campo.name)))
    if isinstance(nuovo, m.Modulo):
        nuovo.sigla = ""  # la sigla dei codici va scelta per il nuovo modulo
    if isinstance(nuovo, m.MetodoStima):
        nuovo.attivo = False
    if isinstance(nuovo, m.SchedaModello):
        nuovo.stato = m.SchedaModello.Stato.BOZZA
    nuovo.save()
    for nome, voci in collegati.items():
        getattr(nuovo, nome).set(voci)
    _copia_figli(originale, nuovo)
    return nuovo


@admin.action(description="Duplica le voci selezionate", permissions=["add"])
def duplica(modeladmin, request, queryset):
    with transaction.atomic():
        copie = [copia(voce) for voce in queryset]
    if len(copie) == 1:
        nuova = copie[0]
        messages.success(request, f"Creata la copia «{nuova}»: controllala e salvala.")
        info = (nuova._meta.app_label, nuova._meta.model_name)
        return HttpResponseRedirect(reverse("admin:%s_%s_change" % info, args=[nuova.pk]))
    messages.success(request, f"Create {len(copie)} copie: " + ", ".join(str(c) for c in copie) + ".")
    return None
