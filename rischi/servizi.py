"""Operazioni sull'analisi: creazione, copia, flusso di approvazione, controlli."""

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .registro import senza_registro_contenuti

from .models import (
    Analisi,
    ApplicabilitaRequisito,
    Esito,
    Figura,
    FiguraMacchina,
    MetodoStima,
    MisuraAnalisi,
    Modulo,
    RequisitoRESS,
    Revisione,
    SchedaAnalisi,
    SchedaModello,
    prossimo_codice,
)

# ---------------------------------------------------------------------------
# Ruoli (gruppi Django)
# ---------------------------------------------------------------------------

COMPILATORE = "Compilatore"
VERIFICATORE = "Verificatore"
APPROVATORE = "Approvatore"
RUOLI = (COMPILATORE, VERIFICATORE, APPROVATORE)


def ha_ruolo(utente, ruolo):
    return utente.is_active and (utente.is_superuser or utente.groups.filter(name=ruolo).exists())


def richiedi_ruolo(utente, ruolo):
    if not ha_ruolo(utente, ruolo):
        raise PermissionDenied(f"Serve il ruolo {ruolo}.")


# ---------------------------------------------------------------------------
# Creazione e copia
# ---------------------------------------------------------------------------


def moduli_attivi(macchina):
    """Moduli scelti per la macchina."""
    return macchina.moduli.filter(attivo=True)


def moduli_proposti():
    """Moduli già selezionati per una nuova commessa."""
    return Modulo.objects.filter(attivo=True, sempre_attivo=True)


_CAMPI_STIMA = (
    "zona_impianto",
    "zona_pericolosa",
    "se_iniziale",
    "fr_iniziale",
    "pr_iniziale",
    "av_iniziale",
    "se_finale",
    "fr_finale",
    "pr_finale",
    "av_finale",
    "testo_istruzioni",
    "note",
)


def _copia_scheda(sorgente, revisione, **extra):
    """Copia una scheda (modello o di un'altra analisi) dentro la revisione."""
    valori = {campo: getattr(sorgente, campo) for campo in _CAMPI_STIMA}
    valori.update(
        revisione=revisione,
        codice=sorgente.codice,
        modulo=sorgente.modulo,
        requisito=_requisito_equivalente(sorgente.requisito, revisione),
    )
    valori.update(extra)
    nuova = SchedaAnalisi.objects.create(**valori)
    nuova.condizioni.set(sorgente.condizioni.all())
    nuova.pericoli.set(sorgente.pericoli.all())
    nuova.norme.set(sorgente.norme.all())
    nuova.soggetti.set(sorgente.soggetti.all())
    for misura in sorgente.misure.all():
        MisuraAnalisi.objects.create(
            scheda=nuova, ordine=misura.ordine, tipo=misura.tipo, testo=misura.testo, norma=misura.norma
        )
    return nuova


def allinea_figure(macchina, revisione, descrizioni=None):
    """Aggiunge alla macchina le figure usate nelle schede, con la descrizione standard o quella data."""
    descrizioni = descrizioni or {}
    usate = Figura.objects.filter(schedaanalisi__revisione=revisione).distinct()
    for figura in usate:
        FiguraMacchina.objects.get_or_create(
            macchina=macchina,
            figura=figura,
            defaults={"descrizione": descrizioni.get(figura.pk, figura.descrizione)},
        )


def codice_scheda(revisione, modulo, escludi=None):
    """Codice di una scheda aggiunta o spostata nell'analisi: numero successivo nel modulo,
    contando le schede della revisione e quelle della libreria."""
    usati = list(SchedaModello.objects.values_list("codice", flat=True))
    schede = revisione.schede.all()
    if escludi:
        schede = schede.exclude(pk=escludi)
    usati += list(schede.values_list("codice", flat=True))
    return prossimo_codice(modulo, usati)


def _requisito_equivalente(requisito, revisione):
    riferimento = revisione.analisi.macchina.commessa.riferimento
    if requisito.riferimento_id == riferimento.pk:
        return requisito
    return RequisitoRESS.objects.get(riferimento=riferimento, codice=requisito.codice)


def _crea_applicabilita(revisione, precedente=None):
    riferimento = revisione.analisi.macchina.commessa.riferimento
    esistenti = {}
    if precedente:
        esistenti = {a.requisito_id: a for a in precedente.applicabilita.all()}
    for requisito in RequisitoRESS.objects.filter(riferimento=riferimento):
        vecchia = esistenti.get(requisito.pk)
        ApplicabilitaRequisito.objects.create(
            revisione=revisione,
            requisito=requisito,
            applicabile=vecchia.applicabile if vecchia else True,
            motivazione=vecchia.motivazione if vecchia else "",
        )


def _metodo_corrente():
    metodo = MetodoStima.corrente()
    if not metodo:
        raise ValidationError("Nessun metodo di stima attivo: importare la libreria.")
    return metodo


@transaction.atomic
def crea_analisi_da_libreria(macchina, utente):
    """Revisione 0 con le schede dei moduli scelti per la macchina."""
    richiedi_ruolo(utente, COMPILATORE)
    analisi = Analisi.objects.create(macchina=macchina, origine=Analisi.Origine.LIBRERIA)
    revisione = Revisione.objects.create(
        analisi=analisi, numero=0, motivo="Prima emissione", metodo=_metodo_corrente(), compilata_da=utente
    )
    schede = SchedaModello.objects.filter(modulo__in=moduli_attivi(macchina)).select_related(
        "modulo", "requisito"
    )
    for scheda in schede:
        _copia_scheda(scheda, revisione, origine=scheda, decisione=SchedaAnalisi.Decisione.PROPOSTA)
    allinea_figure(macchina, revisione)
    _crea_applicabilita(revisione)
    return analisi


@transaction.atomic
def crea_analisi_da_copia(macchina, revisione_sorgente, utente):
    """Revisione 0 copiata da un'altra analisi: le scelte vanno riconfermate."""
    richiedi_ruolo(utente, COMPILATORE)
    analisi = Analisi.objects.create(
        macchina=macchina, origine=Analisi.Origine.COPIA, copiata_da=revisione_sorgente
    )
    revisione = Revisione.objects.create(
        analisi=analisi,
        numero=0,
        motivo=f"Prima emissione, copiata da {revisione_sorgente}",
        metodo=_metodo_corrente(),
        compilata_da=utente,
    )
    for scheda in revisione_sorgente.schede.filter(decisione__in=_DECISIONI_ATTIVE):
        _copia_scheda(scheda, revisione, origine=scheda.origine, decisione=SchedaAnalisi.Decisione.PROPOSTA)
    macchina.moduli.set(revisione_sorgente.analisi.macchina.moduli.all())
    allinea_figure(macchina, revisione, revisione_sorgente.analisi.macchina.descrizioni_figure())
    _crea_applicabilita(revisione, precedente=revisione_sorgente)
    return analisi


@transaction.atomic
def cambia_moduli(macchina, moduli, utente):
    """Cambia i moduli della macchina e allinea la revisione in bozza.

    Le schede dei moduli aggiunti entrano come proposte; quelle dei moduli tolti
    escono solo se ancora da decidere, le altre restano e vanno scartate a mano.
    Restituisce (aggiunte, tolte, rimaste).
    """
    richiedi_ruolo(utente, COMPILATORE)
    analisi = getattr(macchina, "analisi", None)
    revisione = analisi.revisione_corrente if analisi else None
    if revisione and not revisione.modificabile:
        raise ValidationError("I moduli si cambiano solo con una revisione in bozza.")
    prima = set(macchina.moduli.all())
    dopo = set(moduli)
    macchina.moduli.set(dopo)
    if not revisione:
        return 0, 0, 0
    aggiunti, tolti = dopo - prima, prima - dopo
    presenti = set(revisione.schede.values_list("codice", flat=True))
    aggiunte = 0
    for scheda in SchedaModello.objects.filter(modulo__in=aggiunti).exclude(codice__in=presenti):
        _copia_scheda(scheda, revisione, origine=scheda, decisione=SchedaAnalisi.Decisione.PROPOSTA)
        aggiunte += 1
    allinea_figure(macchina, revisione)
    da_togliere = revisione.schede.filter(modulo__in=tolti)
    rimaste = da_togliere.exclude(decisione=SchedaAnalisi.Decisione.PROPOSTA).count()
    tolte = 0
    for scheda in da_togliere.filter(decisione=SchedaAnalisi.Decisione.PROPOSTA):
        scheda.delete()
        tolte += 1
    return aggiunte, tolte, rimaste


_DECISIONI_ATTIVE = (
    SchedaAnalisi.Decisione.PROPOSTA,
    SchedaAnalisi.Decisione.CONFERMATA,
    SchedaAnalisi.Decisione.MODIFICATA,
    SchedaAnalisi.Decisione.AGGIUNTA,
)


@transaction.atomic
def nuova_revisione(analisi, utente, motivo):
    """Apre una nuova bozza copiando l'ultima revisione approvata, scelte comprese."""
    richiedi_ruolo(utente, COMPILATORE)
    if not motivo.strip():
        raise ValidationError("Il motivo della revisione è obbligatorio.")
    corrente = analisi.revisione_corrente
    if corrente.stato != Revisione.Stato.APPROVATA:
        raise ValidationError("Si può aprire una nuova revisione solo dopo l'approvazione della precedente.")
    revisione = Revisione.objects.create(
        analisi=analisi,
        numero=corrente.numero + 1,
        motivo=motivo,
        metodo=_metodo_corrente(),
        compilata_da=utente,
    )
    for scheda in corrente.schede.all():
        _copia_scheda(
            scheda,
            revisione,
            origine=scheda.origine,
            decisione=scheda.decisione,
            motivazione=scheda.motivazione,
            decisa_da=scheda.decisa_da,
            decisa_il=scheda.decisa_il,
        )
    _crea_applicabilita(revisione, precedente=corrente)
    return revisione


# ---------------------------------------------------------------------------
# Decisione sulle schede proposte
# ---------------------------------------------------------------------------


def decidi_scheda(scheda, utente, decisione, motivazione=""):
    richiedi_ruolo(utente, COMPILATORE)
    scheda.decisione = decisione
    scheda.motivazione = motivazione
    scheda.decisa_da = utente
    scheda.decisa_il = timezone.now()
    scheda.full_clean(exclude=["condizioni", "pericoli", "norme", "soggetti"])
    scheda.save()


# ---------------------------------------------------------------------------
# Flusso di approvazione
# ---------------------------------------------------------------------------


def _verifica_stato(revisione, *stati):
    if revisione.stato not in stati:
        raise ValidationError(f"Operazione non possibile: la revisione è {revisione.get_stato_display().lower()}.")


def invia_in_verifica(revisione, utente):
    richiedi_ruolo(utente, COMPILATORE)
    _verifica_stato(revisione, Revisione.Stato.BOZZA)
    revisione.stato = Revisione.Stato.IN_VERIFICA
    revisione.inviata_il = timezone.now()
    revisione.verificata_da = None
    revisione.verificata_il = None
    revisione.save()


def rimanda_in_bozza(revisione, utente, nota):
    if not (ha_ruolo(utente, VERIFICATORE) or ha_ruolo(utente, APPROVATORE)):
        raise PermissionDenied("Serve il ruolo Verificatore o Approvatore.")
    _verifica_stato(revisione, Revisione.Stato.IN_VERIFICA)
    if not nota.strip():
        raise ValidationError("Scrivi cosa va corretto.")
    revisione.stato = Revisione.Stato.BOZZA
    revisione.nota_verifica = nota
    revisione.verificata_da = None
    revisione.verificata_il = None
    revisione.save()


def segna_verificata(revisione, utente):
    richiedi_ruolo(utente, VERIFICATORE)
    _verifica_stato(revisione, Revisione.Stato.IN_VERIFICA)
    revisione.verificata_da = utente
    revisione.verificata_il = timezone.now()
    revisione.save()


@transaction.atomic
def approva(revisione, utente):
    richiedi_ruolo(utente, APPROVATORE)
    _verifica_stato(revisione, Revisione.Stato.IN_VERIFICA)
    if not revisione.verificata_da_id:
        raise ValidationError("La revisione deve essere prima verificata.")
    if revisione.compilata_da_id == utente.pk:
        raise PermissionDenied("Chi ha compilato la revisione non può approvarla.")
    revisione.analisi.revisioni.filter(stato=Revisione.Stato.APPROVATA).update(
        stato=Revisione.Stato.SOSTITUITA
    )
    revisione.stato = Revisione.Stato.APPROVATA
    revisione.approvata_da = utente
    revisione.approvata_il = timezone.now()
    revisione.save()


@transaction.atomic
def elimina_commessa(commessa, utente):
    """Elimina una commessa con macchine, analisi, schede e documenti.

    Una commessa mai approvata la elimina il compilatore; una con revisioni approvate
    (o sostituite) solo l'approvatore. Nel registro restano commessa, macchine, analisi
    e revisioni eliminate, non ogni singola scheda o misura.
    """
    if not puo_eliminare(utente, commessa):
        if ha_revisioni_approvate(commessa):
            raise PermissionDenied(
                f"La commessa {commessa.numero} ha revisioni approvate: può eliminarla solo l'approvatore."
            )
        raise PermissionDenied(f"Serve il ruolo {COMPILATORE}.")
    revisioni = Revisione.objects.filter(analisi__macchina__commessa=commessa)
    for revisione in revisioni:
        for documento in revisione.documenti.all():
            documento.file.delete(save=False)
            documento.delete()
        with senza_registro_contenuti():
            MisuraAnalisi.objects.filter(scheda__revisione=revisione).delete()
            revisione.schede.all().delete()
            revisione.applicabilita.all().delete()
        revisione.delete()
    for macchina in commessa.macchine.all():
        analisi = getattr(macchina, "analisi", None)
        if analisi:
            analisi.delete()
        macchina.delete()
    commessa.delete()


def ha_revisioni_approvate(commessa):
    return Revisione.objects.filter(
        analisi__macchina__commessa=commessa,
        stato__in=(Revisione.Stato.APPROVATA, Revisione.Stato.SOSTITUITA),
    ).exists()


def puo_eliminare(utente, commessa):
    """Compilatore per le commesse mai approvate, approvatore per quelle con revisioni approvate."""
    return ha_ruolo(utente, APPROVATORE if ha_revisioni_approvate(commessa) else COMPILATORE)


# ---------------------------------------------------------------------------
# Controlli di completezza (segnalano, non bloccano)
# ---------------------------------------------------------------------------


@dataclass
class Anomalia:
    tipo: str
    messaggio: str
    scheda: SchedaAnalisi | None = None


def controlli(revisione):
    anomalie = []
    schede = list(
        revisione.schede.select_related("requisito", "revisione__metodo").prefetch_related(
            "misure", "pericoli", "soggetti"
        )
    )
    attive = [s for s in schede if s.attiva]

    requisiti_con_scheda = {s.requisito_id for s in attive}
    for a in revisione.applicabilita.select_related("requisito"):
        if a.applicabile and a.requisito_id not in requisiti_con_scheda:
            anomalie.append(
                Anomalia(
                    "requisito",
                    f"Requisito {a.requisito.codice} {a.requisito.titolo}: nessuna scheda e non segnato come non applicabile.",
                )
            )
        if not a.applicabile and not a.motivazione.strip():
            anomalie.append(
                Anomalia("requisito", f"Requisito {a.requisito.codice}: non applicabile senza motivazione.")
            )

    for s in schede:
        if s.decisione == SchedaAnalisi.Decisione.PROPOSTA:
            anomalie.append(Anomalia("decisione", "Proposta non ancora confermata, modificata o scartata.", s))
    for s in attive:
        if s.pericoli.all() and not s.soggetti.all():
            anomalie.append(Anomalia("soggetti", "Nessun soggetto esposto indicato (operatore o persona esposta).", s))
        if s.ha_stima_iniziale and not s.ha_stima_finale:
            anomalie.append(Anomalia("stima", "Stima iniziale presente ma stima finale mancante.", s))
        if s.ha_stima_finale and s.esito_finale != Esito.OK and not s.testo_istruzioni.strip():
            anomalie.append(
                Anomalia("stima", "Esito finale non verde senza rischio residuo indicato per le istruzioni.", s)
            )
    return anomalie
