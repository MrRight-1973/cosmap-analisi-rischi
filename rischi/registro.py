"""Registro automatico delle modifiche e blocco delle revisioni approvate.

Ogni salvataggio o eliminazione dei modelli elencati in MODELLI_REGISTRATI
scrive una riga in RegistroModifica con l'utente della richiesta corrente.
"""

import threading

from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver
from django.forms.models import model_to_dict

from . import models as m

_locale = threading.local()

MODELLI_REGISTRATI = (
    m.Commessa,
    m.Macchina,
    m.FiguraMacchina,
    m.Analisi,
    m.Revisione,
    m.SchedaAnalisi,
    m.MisuraAnalisi,
    m.ApplicabilitaRequisito,
    m.Modulo,
    m.Figura,
    m.SchedaModello,
    m.MisuraModello,
    m.Norma,
    m.RequisitoRESS,
    m.MetodoStima,
    m.CellaMatrice,
    m.Fabbricante,
    m.LegislazioneUE,
)


_CONTENUTI = (m.SchedaAnalisi, m.MisuraAnalisi, m.ApplicabilitaRequisito)


class senza_registro_contenuti:
    """Non registra una per una schede, misure e applicabilità eliminate insieme alla commessa."""

    def __enter__(self):
        _locale.silenzio = True

    def __exit__(self, *exc):
        _locale.silenzio = False


def utente_corrente():
    return getattr(_locale, "utente", None)


class utente_attivo:
    """Context manager per impostare l'utente fuori da una richiesta web (comandi, test)."""

    def __init__(self, utente):
        self.utente = utente

    def __enter__(self):
        self.precedente = utente_corrente()
        _locale.utente = self.utente

    def __exit__(self, *exc):
        _locale.utente = self.precedente


class UtenteCorrenteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        utente = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        with utente_attivo(utente):
            return self.get_response(request)


def _valori(istanza):
    dati = model_to_dict(istanza)
    return {k: v for k, v in dati.items() if not isinstance(v, list)}


def _serializza(valore):
    if valore is None or isinstance(valore, (bool, int, float, str)):
        return valore
    return str(valore)


@receiver(pre_save)
def _memorizza_prima(sender, instance, **kwargs):
    if sender not in MODELLI_REGISTRATI or not instance.pk:
        return
    precedente = sender.objects.filter(pk=instance.pk).first()
    instance._valori_prima = _valori(precedente) if precedente else None


@receiver(post_save)
def _registra_salvataggio(sender, instance, created, **kwargs):
    if sender not in MODELLI_REGISTRATI or kwargs.get("raw"):
        return
    dopo = _valori(instance)
    if created:
        modifiche = {k: [None, _serializza(v)] for k, v in dopo.items() if v not in (None, "")}
        azione = m.RegistroModifica.Azione.CREA
    else:
        prima = getattr(instance, "_valori_prima", None) or {}
        modifiche = {
            k: [_serializza(prima.get(k)), _serializza(v)] for k, v in dopo.items() if prima.get(k) != v
        }
        if not modifiche:
            return
        azione = m.RegistroModifica.Azione.MODIFICA
    m.RegistroModifica.objects.create(
        utente=utente_corrente(),
        azione=azione,
        tabella=sender._meta.verbose_name,
        oggetto_id=str(instance.pk),
        descrizione=str(instance)[:300],
        modifiche=modifiche,
    )


@receiver(post_delete)
def _registra_eliminazione(sender, instance, **kwargs):
    if sender not in MODELLI_REGISTRATI:
        return
    if sender in _CONTENUTI and getattr(_locale, "silenzio", False):
        return
    m.RegistroModifica.objects.create(
        utente=utente_corrente(),
        azione=m.RegistroModifica.Azione.ELIMINA,
        tabella=sender._meta.verbose_name,
        oggetto_id=str(instance.pk),
        descrizione=str(instance)[:300],
        modifiche={k: [_serializza(v), None] for k, v in _valori(instance).items()},
    )


@receiver(m2m_changed)
def _blocca_e_registra_m2m(sender, instance, action, model, pk_set, **kwargs):
    if not isinstance(instance, m.SchedaAnalisi) or action not in ("pre_add", "pre_remove", "pre_clear", "post_add", "post_remove"):
        return
    if action.startswith("pre_"):
        instance.revisione.verifica_modificabile()
        return
    campo = model._meta.verbose_name_plural
    elementi = ", ".join(str(o) for o in model.objects.filter(pk__in=pk_set or []))[:250]
    m.RegistroModifica.objects.create(
        utente=utente_corrente(),
        azione=m.RegistroModifica.Azione.MODIFICA,
        tabella=m.SchedaAnalisi._meta.verbose_name,
        oggetto_id=str(instance.pk),
        descrizione=str(instance)[:300],
        modifiche={campo: ["aggiunti" if action == "post_add" else "tolti", elementi]},
    )
