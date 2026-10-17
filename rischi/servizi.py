"""Operazioni sull'analisi: creazione, copia, flusso di approvazione, controlli."""

import re
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max as models_Max
from django.db.models import Q
from django.utils import timezone

from .registro import senza_registro_contenuti
from . import calcolo

from .models import (
    Analisi,
    AllegatoAnalisi,
    ArticoloSicurezza,
    ApplicabilitaRequisito,
    Esito,
    Figura,
    FiguraMacchina,
    FunzioneSicurezza,
    MetodoStima,
    MisuraAnalisi,
    Modulo,
    ProveFunzione,
    RequisitoRESS,
    Revisione,
    SchedaAnalisi,
    SchedaModello,
    ValidazioneSicurezza,
    ValutazioneFunzione,
    VerificaElettrica,
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
    "stampa_note_requisito",
    "considerazioni_limiti",
    "considerazioni_pericoli",
    "considerazioni_soggetti",
    "considerazioni_stima_iniziale",
    "considerazioni_riduzione",
    "considerazioni_stima_finale",
)


def _copia_scheda(sorgente, revisione, mappa_misure=None, **extra):
    """Copia una scheda (modello o di un'altra analisi) dentro la revisione.

    In mappa_misure, se data, scrive misura originale -> misura copiata (per ricollegare le funzioni di sicurezza)."""
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
    nuova.norme_escluse.set(sorgente.norme_escluse.all())
    nuova.soggetti.set(sorgente.soggetti.all())
    for allegato in sorgente.allegati.all():
        AllegatoAnalisi.objects.create(
            scheda=nuova, file=allegato.file.name, testo=allegato.testo, allineamento=allegato.allineamento,
            posizione_testo=allegato.posizione_testo, ordine=allegato.ordine
        )
    for misura in sorgente.misure.all():
        copia = MisuraAnalisi.objects.create(
            scheda=nuova, ordine=misura.ordine, tipo=misura.tipo, testo=misura.testo, norma=misura.norma,
            soluzione=misura.soluzione
        )
        if mappa_misure is not None:
            mappa_misure[misura.pk] = copia
    return nuova


def _copia_funzioni(sorgente, revisione, mappa_misure, stessa_macchina):
    """Copia funzioni di sicurezza e valutazioni nella revisione, collegate alle misure copiate; restituisce
    {pk della funzione di partenza: funzione copiata}.

    Le prove di validazione si copiano a parte (_copia_validazione) e solo sulla stessa macchina."""
    mappa = {}
    for funzione in sorgente.funzioni.all():
        nuova = FunzioneSicurezza.objects.create(
            revisione=revisione, ordine=funzione.ordine, nome=funzione.nome, descrizione=funzione.descrizione,
            s=funzione.s, f=funzione.f, p=funzione.p,
        )
        mappa[funzione.pk] = nuova
        nuova.misure.set([mappa_misure[mi.pk] for mi in funzione.misure.all() if mi.pk in mappa_misure])
        valutazione = getattr(funzione, "valutazione", None)
        if valutazione is None:
            continue
        dettaglio = dict(valutazione.dettaglio)
        if not stessa_macchina:
            dettaglio.pop("validazione", None)  # esiti delle prove nel formato della safety evaluation
        ValutazioneFunzione.objects.create(
            funzione=nuova, dettaglio=dettaglio, pl=valutazione.pl, pfh=valutazione.pfh, esito=valutazione.esito,
            calcolata_il=valutazione.calcolata_il,
        )
    return mappa


def _copia_validazione(sorgente, revisione, mappa_funzioni):
    """La nuova revisione riparte dalla validazione della precedente, in bozza: le prove già fatte restano
    compilate e si confermano o si rifanno dove la revisione ha cambiato le funzioni."""
    precedente = getattr(sorgente, "validazione", None)
    if precedente is None:
        return
    validazione = ValidazioneSicurezza.objects.create(revisione=revisione, sistematiche=precedente.sistematiche)
    for prove in precedente.prove.all():
        if prove.funzione_id in mappa_funzioni:
            ProveFunzione.objects.create(
                validazione=validazione, funzione=mappa_funzioni[prove.funzione_id], dati=prove.dati,
                validata=prove.validata, da_eseguire=prove.da_eseguire, non_ok=prove.non_ok,
            )


@transaction.atomic
def aggiorna_da_modello(scheda, utente):
    """Ricarica nella scheda della commessa il contenuto attuale della sua scheda modello in libreria.

    Zone, condizioni, pericoli, soggetti, stime, misure, norme, note e considerazioni sono sostituiti da quelli
    della scheda modello; modulo, requisito, codice e decisione della scheda restano invariati."""
    richiedi_ruolo(utente, COMPILATORE)
    if not scheda.revisione.modificabile:
        raise ValidationError("La scheda si aggiorna solo con una revisione in bozza.")
    modello = scheda.origine
    if modello is None:
        raise ValidationError("La scheda è stata aggiunta a mano e non ha una scheda modello.")
    for campo in _CAMPI_STIMA:
        setattr(scheda, campo, getattr(modello, campo))
    scheda.save()
    scheda.condizioni.set(modello.condizioni.all())
    scheda.pericoli.set(modello.pericoli.all())
    scheda.norme.set(modello.norme.all())
    scheda.norme_escluse.set(modello.norme_escluse.all())
    scheda.soggetti.set(modello.soggetti.all())
    # Le funzioni di sicurezza collegate alle misure sostituite passano alla nuova misura con lo stesso testo,
    # altrimenti a quella nella stessa posizione
    collegate = [(mi.testo, mi.ordine, list(mi.funzioni.all())) for mi in scheda.misure.all()]
    scheda.misure.all().delete()
    # Il file resta: può essere lo stesso della scheda modello o di altre schede
    scheda.allegati.all().delete()
    for allegato in modello.allegati.all():
        AllegatoAnalisi.objects.create(
            scheda=scheda, file=allegato.file.name, testo=allegato.testo, allineamento=allegato.allineamento,
            posizione_testo=allegato.posizione_testo, ordine=allegato.ordine
        )
    for misura in modello.misure.all():
        MisuraAnalisi.objects.create(
            scheda=scheda, ordine=misura.ordine, tipo=misura.tipo, testo=misura.testo, norma=misura.norma,
            soluzione=misura.soluzione
        )
    nuove = list(scheda.misure.all())
    for testo, ordine, funzioni in collegate:
        misura = next((mi for mi in nuove if mi.testo == testo), None) or next(
            (mi for mi in nuove if mi.ordine == ordine), None
        )
        if misura:
            misura.funzioni.add(*funzioni)
    allinea_figure(scheda.revisione.analisi.macchina, scheda.revisione)
    return modello


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
    allinea_applicabilita(revisione.analisi.macchina, revisione)


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
    schede = schede_attive(macchina).select_related("modulo", "requisito")
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
    mappa_misure = {}
    for scheda in revisione_sorgente.schede.filter(decisione__in=_DECISIONI_ATTIVE):
        _copia_scheda(
            scheda, revisione, mappa_misure, origine=scheda.origine, decisione=SchedaAnalisi.Decisione.PROPOSTA
        )
    _copia_funzioni(revisione_sorgente, revisione, mappa_misure, stessa_macchina=False)
    macchina.moduli.set(revisione_sorgente.analisi.macchina.moduli.all())
    macchina.schede_escluse.set(revisione_sorgente.analisi.macchina.schede_escluse.all())
    macchina.norme_tipo_c.set(revisione_sorgente.analisi.macchina.norme_tipo_c.all())
    allinea_figure(macchina, revisione, revisione_sorgente.analisi.macchina.descrizioni_figure())
    _crea_applicabilita(revisione, precedente=revisione_sorgente)
    return analisi


def schede_attive(macchina):
    """Schede modello che entrano nell'analisi: quelle dei moduli scelti, tranne le escluse a mano e quelle
    dei requisiti non considerati per la macchina."""
    return (
        SchedaModello.objects.filter(modulo__in=moduli_attivi(macchina))
        .exclude(pk__in=macchina.schede_escluse.values("pk"))
        .exclude(requisito__codice__in=macchina.requisiti_esclusi.values("codice"))
    )


def schede_attive_libreria(macchina):
    """Schede modello spuntate nella pagina della macchina: tutte quelle della libreria, tranne le escluse
    (anche per i moduli non scelti, così riattivando un modulo tornano le sue schede di prima)."""
    return SchedaModello.objects.exclude(pk__in=macchina.schede_escluse.values("pk"))


@transaction.atomic
def cambia_moduli(macchina, moduli, utente, escluse=None, requisiti_esclusi=None):
    """Cambia i moduli della macchina (e, se date, le schede modello escluse e i requisiti non considerati) e
    allinea la revisione in bozza.

    Le schede che diventano attive entrano come proposte; quelle che non lo sono più escono solo se ancora da
    decidere, le altre restano e vanno scartate a mano. I requisiti non considerati risultano non applicabili.
    Restituisce (aggiunte, tolte, rimaste).
    """
    richiedi_ruolo(utente, COMPILATORE)
    analisi = getattr(macchina, "analisi", None)
    revisione = analisi.revisione_corrente if analisi else None
    if revisione and not revisione.modificabile:
        raise ValidationError("I moduli si cambiano solo con una revisione in bozza.")
    prima = set(macchina.moduli.all())
    attive_prima = set(schede_attive(macchina).values_list("pk", flat=True))
    dopo = set(moduli)
    macchina.moduli.set(dopo)
    if escluse is not None:
        macchina.schede_escluse.set(escluse)
    if requisiti_esclusi is not None:
        macchina.requisiti_esclusi.set(requisiti_esclusi)
    attive_dopo = set(schede_attive(macchina).values_list("pk", flat=True))
    if not revisione:
        return 0, 0, 0
    tolti = prima - dopo
    da_aggiungere = (
        SchedaModello.objects.filter(pk__in=attive_dopo - attive_prima)
        .exclude(codice__in=revisione.schede.values("codice"))
        .exclude(pk__in=revisione.schede.exclude(origine=None).values("origine"))
    )
    aggiunte = 0
    for scheda in da_aggiungere:
        _copia_scheda(scheda, revisione, origine=scheda, decisione=SchedaAnalisi.Decisione.PROPOSTA)
        aggiunte += 1
    allinea_figure(macchina, revisione)
    allinea_applicabilita(macchina, revisione)
    da_togliere = revisione.schede.filter(Q(modulo__in=tolti) | Q(origine__in=attive_prima - attive_dopo))
    rimaste = da_togliere.exclude(decisione=SchedaAnalisi.Decisione.PROPOSTA).count()
    tolte = 0
    for scheda in da_togliere.filter(decisione=SchedaAnalisi.Decisione.PROPOSTA):
        scheda.delete()
        tolte += 1
    return aggiunte, tolte, rimaste


MOTIVO_NON_CONSIDERATO = "Requisito non considerato per questa macchina (Dati della macchina e moduli)."


def allinea_applicabilita(macchina, revisione):
    """I requisiti non considerati per la macchina diventano non applicabili; quelli considerati di nuovo
    tornano applicabili se erano stati esclusi da qui (le motivazioni scritte a mano restano)."""
    esclusi = set(macchina.requisiti_esclusi.values_list("codice", flat=True))
    for voce in revisione.applicabilita.select_related("requisito"):
        if voce.requisito.codice in esclusi:
            if voce.applicabile or not voce.motivazione.strip():
                voce.applicabile = False
                voce.motivazione = voce.motivazione.strip() or MOTIVO_NON_CONSIDERATO
                voce.save()
        elif not voce.applicabile and voce.motivazione == MOTIVO_NON_CONSIDERATO:
            voce.applicabile = True
            voce.motivazione = ""
            voce.save()


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
    mappa_misure = {}
    for scheda in corrente.schede.all():
        _copia_scheda(
            scheda,
            revisione,
            mappa_misure,
            origine=scheda.origine,
            decisione=scheda.decisione,
            motivazione=scheda.motivazione,
            decisa_da=scheda.decisa_da,
            decisa_il=scheda.decisa_il,
        )
    mappa_funzioni = _copia_funzioni(corrente, revisione, mappa_misure, stessa_macchina=True)
    _copia_validazione(corrente, revisione, mappa_funzioni)
    _copia_verifiche_elettriche(corrente, revisione)
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
# Calcolo del PL delle funzioni di sicurezza
# ---------------------------------------------------------------------------


@transaction.atomic
def salva_valutazione(funzione, dettaglio, risultato_pagina, utente):
    """Salva il dettaglio del calcolo e i risultati. I risultati vengono dal ricalcolo del server con engine.js;
    senza Node sul server restano quelli della pagina, e il messaggio lo dice."""
    richiedi_ruolo(utente, COMPILATORE)
    funzione.revisione.verifica_modificabile()
    valutazione = getattr(funzione, "valutazione", None) or ValutazioneFunzione(funzione=funzione)
    precedente = valutazione.dettaglio if valutazione.pk else {}
    # Le parti del dettaglio che la pagina non gestisce (es. le prove di validazione) restano
    valutazione.dettaglio = {**precedente, **dettaglio}
    prove_auto = None
    try:
        r = calcolo.calcola(funzione, valutazione.dettaglio)
        pl, pfh, esito, prove_auto = r["pl"], r["pfh"], r["ok"], r["prove"]
        messaggio = "Valutazione salvata e ricalcolata dal server"
    except calcolo.CalcoloNonRiuscito as errore:
        if risultato_pagina:
            pl, pfh, esito = risultato_pagina.get("pl"), risultato_pagina.get("pfh"), risultato_pagina.get("ok")
        else:  # S, F o P cambiati nella pagina della funzione: il confronto va rifatto aprendo il calcolo
            pl, pfh, esito = valutazione.pl, valutazione.pfh, None
        messaggio = f"Valutazione salvata con il calcolo della pagina ({errore})"
    valutazione.pl = pl if pl in ("a", "b", "c", "d", "e") else ""  # engine.js dà "nessuno" oltre la PL a
    valutazione.pfh = pfh
    valutazione.esito = bool(esito) if esito is not None else None
    valutazione.calcolata_il = timezone.now()
    valutazione.save()
    prove = ProveFunzione.objects.filter(funzione=funzione).select_related("validazione__revisione").first()
    if prove_auto is not None and prove is not None and prove.validazione.modificabile:
        _aggiorna_conteggi(prove, prove_auto)  # lo schema può aver cambiato le prove standard
        prove.save()
    chiavi = {
        c.get("articoloId") for ss in valutazione.dettaglio.get("sottosistemi", []) for c in ss.get("componenti", [])
    } - {None, ""}
    oggi = timezone.localdate()
    for articolo in ArticoloSicurezza.objects.filter(chiave__in=chiavi).exclude(utilizzato=oggi):
        articolo.utilizzato = oggi
        articolo.save(update_fields=["utilizzato"])
    esito_testo = "PL " + valutazione.pl if valutazione.pl else "PL non ancora calcolabile"
    if valutazione.esito:
        esito_testo += f" ≥ PLr {funzione.plr}"
    elif valutazione.pl and funzione.plr:
        esito_testo += f", requisito PLr {funzione.plr} non dimostrato"
    return {"messaggio": f"{messaggio}: {esito_testo}.", "pl": valutazione.pl, "pfh": valutazione.pfh, "ok": valutazione.esito}


# ---------------------------------------------------------------------------
# Validazione delle funzioni di sicurezza (EN ISO 13849-2): flusso proprio
# ---------------------------------------------------------------------------

ESITI_PROVA = ("", "ok", "ko", "na")


def validazione_di(revisione):
    """La validazione della revisione; se non è ancora stata compilata, una nuova non salvata."""
    return getattr(revisione, "validazione", None) or ValidazioneSicurezza(revisione=revisione)


def riepilogo_prove(prove_auto, dati):
    """Conteggi come Validazione.riepilogo di validazione.js: prove standard ricavate dallo schema più quelle
    aggiunte a mano. Completa quando ogni prova applicabile è OK."""
    esiti = dati.get("esiti") or {}
    chiavi = [p["key"] for p in prove_auto] + [f"extra:{x.get('id')}" for x in dati.get("extra") or []]
    valori = [(esiti.get(k) or {}).get("esito") or "" for k in chiavi]
    r = {"totali": len(chiavi), "ok": valori.count("ok"), "ko": valori.count("ko"), "na": valori.count("na"),
         "aperte": valori.count("")}
    r["completa"] = r["totali"] > 0 and r["ko"] == 0 and r["aperte"] == 0
    return r


def _aggiorna_conteggi(prove, prove_auto):
    r = riepilogo_prove(prove_auto, prove.dati)
    prove.validata, prove.da_eseguire, prove.non_ok = r["completa"], r["aperte"], r["ko"]
    return r


def _testo(valore, massimo=2000):
    if valore is None:
        return ""
    if not isinstance(valore, str):
        raise ValidationError("Dati non validi.")
    return valore.strip()[:massimo]


def _esiti_puliti(esiti, campi=("esito", "note")):
    if not isinstance(esiti, dict):
        raise ValidationError("Esiti non validi.")
    puliti = {}
    for chiave, valore in esiti.items():
        if not isinstance(valore, dict) or valore.get("esito", "") not in ESITI_PROVA:
            raise ValidationError(f"Esito non valido per «{chiave}».")
        voce = {k: _testo(valore.get(k)) for k in campi if valore.get(k)}
        if voce:
            puliti[str(chiave)[:100]] = voce
    return puliti


@transaction.atomic
def salva_prove(funzione, dati, prove_pagina, utente):
    """Esiti delle prove di validazione della funzione. Le prove standard vengono dallo schema a blocchi, ricalcolate
    dal server con validazione.js; senza Node valgono quelle della pagina."""
    richiedi_ruolo(utente, COMPILATORE)
    validazione = validazione_di(funzione.revisione)
    validazione.verifica_modificabile()
    if not validazione.pk:
        validazione.save()
    extra = dati.get("extra") or []
    if not isinstance(extra, list) or not all(isinstance(x, dict) and x.get("id") for x in extra):
        raise ValidationError("Prove aggiunte non valide.")
    data = _testo(dati.get("data"), 10)
    if data and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
        raise ValidationError("Data non valida.")
    prove = getattr(funzione, "prove", None) or ProveFunzione(validazione=validazione, funzione=funzione)
    prove.dati = {
        **prove.dati,
        "esiti": _esiti_puliti(dati.get("esiti") or {}),
        "extra": [{"id": _testo(x["id"], 20), "testo": _testo(x.get("testo")), "atteso": _testo(x.get("atteso"))} for x in extra],
        "esecutore": _testo(dati.get("esecutore"), 200),
        "data": data,
    }
    try:
        dettaglio = funzione.valutazione.dettaglio if hasattr(funzione, "valutazione") else {}
        prove_auto = calcolo.calcola(funzione, dettaglio)["prove"]
        messaggio = "Prove salvate"
    except calcolo.CalcoloNonRiuscito as errore:
        prove_auto = [p for p in prove_pagina if isinstance(p, dict) and isinstance(p.get("key"), str)]
        messaggio = f"Prove salvate con l'elenco della pagina ({errore})"
    r = _aggiorna_conteggi(prove, prove_auto)
    prove.save()
    if r["completa"]:
        stato = "funzione validata"
    else:
        parti = [f"{r['aperte']} da eseguire" if r["aperte"] else "", f"{r['ko']} non OK" if r["ko"] else ""]
        stato = ", ".join(p for p in parti if p) or "nessuna prova"
    return {"messaggio": f"{messaggio}: {stato}.", "riepilogo": r}


@transaction.atomic
def salva_sistematiche(revisione, dati, utente):
    """Misure contro i guasti sistematici (EN ISO 13849-1, all. G), versione e firma del programma F."""
    richiedi_ruolo(utente, COMPILATORE)
    validazione = validazione_di(revisione)
    validazione.verifica_modificabile()
    validazione.sistematiche = {
        **validazione.sistematiche,
        "esiti": _esiti_puliti(dati.get("esiti") or {}),
        "swVersione": _testo(dati.get("swVersione"), 200),
        "swFirma": _testo(dati.get("swFirma"), 200),
    }
    validazione.save()
    return {"messaggio": "Misure contro i guasti sistematici salvate."}


def _verifica_stato_flusso(oggetto, *stati):
    if not oggetto.pk or oggetto.stato not in stati:
        stato = oggetto.get_stato_display().lower() if oggetto.pk else "non ancora compilata"
        raise ValidationError(f"Operazione non possibile: {oggetto.NOME} è {stato}.")


def _invia(oggetto, utente):
    """Flusso proprio di validazione e verifiche elettriche, come quello della revisione."""
    richiedi_ruolo(utente, COMPILATORE)
    oggetto.verifica_modificabile()
    oggetto.stato = oggetto.Stato.IN_VERIFICA
    oggetto.inviata_da = utente
    oggetto.inviata_il = timezone.now()
    oggetto.verificata_da = None
    oggetto.verificata_il = None
    oggetto.save()


def _rimanda(oggetto, utente, nota):
    if not (ha_ruolo(utente, VERIFICATORE) or ha_ruolo(utente, APPROVATORE)):
        raise PermissionDenied("Serve il ruolo Verificatore o Approvatore.")
    _verifica_stato_flusso(oggetto, oggetto.Stato.IN_VERIFICA)
    if not nota.strip():
        raise ValidationError("Scrivi cosa va corretto.")
    oggetto.stato = oggetto.Stato.BOZZA
    oggetto.nota_verifica = nota
    oggetto.verificata_da = None
    oggetto.verificata_il = None
    oggetto.save()


def _segna_verificata(oggetto, utente):
    richiedi_ruolo(utente, VERIFICATORE)
    _verifica_stato_flusso(oggetto, oggetto.Stato.IN_VERIFICA)
    oggetto.verificata_da = utente
    oggetto.verificata_il = timezone.now()
    oggetto.save()


def _verifica_approvabile(oggetto, utente):
    richiedi_ruolo(utente, APPROVATORE)
    _verifica_stato_flusso(oggetto, oggetto.Stato.IN_VERIFICA)
    if not oggetto.verificata_da_id:
        raise ValidationError(f"{oggetto.NOME.capitalize()} deve essere prima verificata.")
    if oggetto.inviata_da_id == utente.pk:
        raise PermissionDenied(f"Chi ha compilato {oggetto.NOME} non può approvarla.")


def _approva(oggetto, utente):
    oggetto.stato = oggetto.Stato.APPROVATA
    oggetto.approvata_da = utente
    oggetto.approvata_il = timezone.now()
    oggetto.save()


def invia_validazione(revisione, utente):
    if not revisione.funzioni.exists():
        raise ValidationError("La revisione non ha funzioni di sicurezza da validare.")
    _invia(validazione_di(revisione), utente)


def rimanda_validazione(revisione, utente, nota):
    _rimanda(validazione_di(revisione), utente, nota)


def verifica_validazione(revisione, utente):
    _segna_verificata(validazione_di(revisione), utente)


def approva_validazione(revisione, utente):
    validazione = validazione_di(revisione)
    _verifica_approvabile(validazione, utente)
    if revisione.stato != Revisione.Stato.APPROVATA:
        raise ValidationError(
            f"Approva prima la revisione {revisione.numero} dell'analisi: la validazione si riferisce alle funzioni "
            "e ai calcoli approvati."
        )
    _approva(validazione, utente)


@dataclass
class RigaValidazione:
    funzione: FunzioneSicurezza
    risultato: dict | None  # dal motore (None senza Node)
    prove: list  # prove standard e aggiunte, con esito e note
    riepilogo: dict

    @property
    def eseguite(self):
        """"M. Rossi · 17/10/2026" dai dati delle prove."""
        dati = self.funzione.prove.dati if hasattr(self.funzione, "prove") else {}
        data = dati.get("data") or ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", data):
            data = "/".join(reversed(data.split("-")))
        return " · ".join(x for x in (dati.get("esecutore"), data) if x)


def quadro_validazione(revisione):
    """Funzioni con prove ed esiti, misure sistematiche e controlli, per la pagina della validazione e la relazione.
    Prove e calcoli si ricavano dal motore (Node); senza Node restano i conteggi salvati e manca il dettaglio."""
    validazione = validazione_di(revisione)
    funzioni = list(revisione.funzioni.select_related("valutazione", "prove").prefetch_related("misure__scheda"))
    try:
        risultati, sistematiche = calcolo.analizza(funzioni)
    except calcolo.CalcoloNonRiuscito:
        risultati, sistematiche = None, None
    righe = []
    for funzione in funzioni:
        prove = getattr(funzione, "prove", None)
        dati = prove.dati if prove else {}
        risultato = risultati.get(funzione.pk) if risultati else None
        esiti = dati.get("esiti") or {}
        if risultato:
            elenco = [{**p, **(esiti.get(p["key"]) or {})} for p in risultato["prove"]]
            elenco += [
                {"key": f"extra:{x['id']}", "testo": x.get("testo", ""), "atteso": x.get("atteso", ""), **(esiti.get(f"extra:{x['id']}") or {})}
                for x in dati.get("extra") or []
            ]
            riepilogo = riepilogo_prove(risultato["prove"], dati)
        else:
            elenco = []
            riepilogo = {
                "totali": None, "ok": None, "na": None, "ko": prove.non_ok if prove else 0,
                "aperte": prove.da_eseguire if prove else None, "completa": bool(prove and prove.validata),
            }
        righe.append(RigaValidazione(funzione, risultato, elenco, riepilogo))
    return {
        "validazione": validazione, "righe": righe, "sistematiche": sistematiche,
        "anomalie": controlli_validazione(revisione, validazione, righe, sistematiche),
    }


def controlli_validazione(revisione, validazione, righe, sistematiche):
    anomalie = []
    if revisione.stato != Revisione.Stato.APPROVATA:
        anomalie.append(Anomalia(
            "revisione", f"La revisione {revisione.numero} dell'analisi non è approvata: la validazione si approva dopo."
        ))
    esiti = (validazione.sistematiche or {}).get("esiti") or {}
    if sistematiche is not None:
        chiavi = [m[0] for g in sistematiche for m in g["misure"]]
        mancanti = sum(1 for k in chiavi if not (esiti.get(k) or {}).get("esito"))
        if mancanti:
            anomalie.append(Anomalia("sistematiche", f"Misure contro i guasti sistematici: {mancanti} senza esito."))
    non_ok = sum(1 for e in esiti.values() if e.get("esito") == "ko")
    if non_ok:
        anomalie.append(Anomalia("sistematiche", f"Misure contro i guasti sistematici: {non_ok} non OK."))
    for riga in righe:
        nome, r = riga.funzione.nome, riga.riepilogo
        if r["completa"]:
            continue
        if not hasattr(riga.funzione, "prove"):
            anomalie.append(Anomalia("prove", f"Funzione «{nome}»: prove di validazione non ancora compilate."))
            continue
        if r["aperte"]:
            anomalie.append(Anomalia("prove", f"Funzione «{nome}»: {r['aperte']} prove da eseguire."))
        if r["ko"]:
            anomalie.append(Anomalia("prove", f"Funzione «{nome}»: {r['ko']} prove non OK."))
        if r["totali"] == 0:
            anomalie.append(Anomalia("prove", f"Funzione «{nome}»: nessuna prova (schema a blocchi vuoto)."))
    for riga in righe:
        dati = riga.funzione.prove.dati if hasattr(riga.funzione, "prove") else {}
        if dati and not (dati.get("esecutore") and dati.get("data")):
            anomalie.append(Anomalia("prove", f"Funzione «{riga.funzione.nome}»: indicare chi ha eseguito le prove e quando."))
    return anomalie


# ---------------------------------------------------------------------------
# Verifiche elettriche (IEC 60204-1, cap. 18): una per quadro, flusso proprio
# ---------------------------------------------------------------------------

CAMPI_TESTATA = ("tensione", "strumento", "taratura", "vprova", "esecutore", "data")
COLONNE_REGISTRO = {
    "equipotenziali": ("punto", "conduttore", "sezione", "rpe", "note"),
    "cavi": ("sigla", "percorso", "tipo", "formazione", "sezione", "protezione", "in", "zs",
             "l1pe", "l2pe", "l3pe", "l1l2", "l1l3", "l2l3", "rpe", "note"),
}
MASSIMO_RIGHE = 2000


def _verifica_ultima_revisione(revisione):
    if revisione.analisi.revisioni.filter(numero__gt=revisione.numero).exists():
        raise ValidationError("Esiste una revisione più recente dell'analisi: le verifiche si compilano in quella.")


def nuova_verifica_elettrica(revisione, quadro, utente):
    richiedi_ruolo(utente, COMPILATORE)
    _verifica_ultima_revisione(revisione)
    quadro = _testo(quadro, 200)
    if not quadro:
        raise ValidationError("Scrivi il nome dell'equipaggiamento o del quadro.")
    ordine = (revisione.verifiche_elettriche.aggregate(m=models_Max("ordine"))["m"] or 0) + 1
    return VerificaElettrica.objects.create(revisione=revisione, quadro=quadro, ordine=ordine)


def elimina_verifica_elettrica(verifica, utente):
    richiedi_ruolo(utente, COMPILATORE)
    verifica.verifica_modificabile()
    if verifica.approvata_il:
        raise ValidationError("Una verifica già approvata non si elimina.")
    verifica.delete()


def _righe_registro(righe, colonne):
    if not isinstance(righe, list) or len(righe) > MASSIMO_RIGHE:
        raise ValidationError("Registro misure non valido.")
    pulite = []
    for riga in righe:
        if not isinstance(riga, dict):
            raise ValidationError("Registro misure non valido.")
        pulita = {"id": _testo(str(riga.get("id") or ""), 20)}
        pulita.update({k: _testo(riga.get(k), 200) for k in colonne if riga.get(k)})
        pulite.append(pulita)
    return pulite


def _conteggi_verifica(verifica, risultato):
    verifica.da_eseguire = risultato["riepilogo"]["aperte"]
    verifica.non_ok = risultato["riepilogo"]["ko"]
    verifica.isolamento_non_ok = len(risultato["registro"]["isoKo"])


@transaction.atomic
def salva_verifica_elettrica(verifica, quadro, dati, risultato_pagina, utente):
    """Testata, prove con valore ed esito, punti di misura aggiunti e registro misure. I conteggi (prove da eseguire
    o non OK, cavi con isolamento non OK) vengono da validazione.js eseguito dal server; senza Node da quelli della
    pagina."""
    richiedi_ruolo(utente, COMPILATORE)
    verifica.verifica_modificabile()
    quadro = _testo(quadro, 200)
    if not quadro:
        raise ValidationError("Scrivi il nome dell'equipaggiamento o del quadro.")
    extra = dati.get("extra") or []
    if not isinstance(extra, list) or not all(isinstance(x, dict) and x.get("id") for x in extra):
        raise ValidationError("Punti di misura aggiunti non validi.")
    for campo in ("taratura", "data"):
        valore = _testo(dati.get(campo), 10)
        if valore and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valore):
            raise ValidationError("Data non valida.")
    verifica.quadro = quadro
    verifica.dati = {
        **{k: _testo(dati.get(k), 200) for k in CAMPI_TESTATA},
        "esiti": _esiti_puliti(dati.get("esiti") or {}, ("esito", "note", "misurato")),
        "extra": [
            {"id": _testo(str(x["id"]), 20), **{k: _testo(x.get(k), 500) for k in ("testo", "criterio", "unita")}}
            for x in extra
        ],
        **{chiave: _righe_registro(dati.get(chiave) or [], colonne) for chiave, colonne in COLONNE_REGISTRO.items()},
    }
    try:
        risultato = calcolo.elettriche(verifica.dati)
        messaggio = "Verifica salvata"
    except calcolo.CalcoloNonRiuscito as errore:
        risultato = risultato_pagina
        messaggio = f"Verifica salvata con i conteggi della pagina ({errore})"
    try:
        _conteggi_verifica(verifica, risultato)
    except (KeyError, TypeError):
        raise ValidationError("Riepilogo della pagina non valido.")
    verifica.save()
    parti = [
        f"{verifica.da_eseguire} prove da eseguire" if verifica.da_eseguire else "",
        f"{verifica.non_ok} non OK" if verifica.non_ok else "",
        f"isolamento non OK su {verifica.isolamento_non_ok} cavi" if verifica.isolamento_non_ok else "",
    ]
    return {"messaggio": f"{messaggio}: {', '.join(p for p in parti if p) or 'tutte le prove eseguite'}."}


def invia_verifica_elettrica(verifica, utente):
    _invia(verifica, utente)


def rimanda_verifica_elettrica(verifica, utente, nota):
    _rimanda(verifica, utente, nota)


def segna_verifica_elettrica_verificata(verifica, utente):
    _segna_verificata(verifica, utente)


def approva_verifica_elettrica(verifica, utente):
    _verifica_approvabile(verifica, utente)
    _approva(verifica, utente)


def controlli_verifica_elettrica(verifica, risultato=None):
    """Segnalazioni della verifica; con il risultato del motore anche il dettaglio del registro."""
    anomalie = []
    dati = verifica.dati or {}
    if risultato:
        r = risultato["riepilogo"]
        if r["aperte"]:
            anomalie.append(Anomalia("prove", f"{r['aperte']} prove senza esito."))
        if r["ko"]:
            anomalie.append(Anomalia("prove", f"{r['ko']} prove non OK."))
        registro = risultato["registro"]
        if registro["isoKo"]:
            anomalie.append(Anomalia("isolamento", f"Isolamento sotto {risultato['isoMin']} MΩ: {', '.join(registro['isoKo'])}."))
        if registro["senzaMisure"]:
            anomalie.append(Anomalia("registro", f"Registro misure: {registro['senzaMisure']} righe senza valori misurati."))
    else:
        if verifica.da_eseguire:
            anomalie.append(Anomalia("prove", f"{verifica.da_eseguire} prove senza esito."))
        if verifica.non_ok:
            anomalie.append(Anomalia("prove", f"{verifica.non_ok} prove non OK."))
        if verifica.isolamento_non_ok:
            anomalie.append(Anomalia("isolamento", f"Isolamento non OK su {verifica.isolamento_non_ok} cavi."))
    if not dati.get("strumento"):
        anomalie.append(Anomalia("strumento", "Indicare lo strumento (modello, matricola)."))
    if not dati.get("taratura"):
        anomalie.append(Anomalia("strumento", "Indicare la scadenza della taratura dello strumento."))
    elif dati.get("data") and dati["taratura"] < dati["data"]:
        anomalie.append(Anomalia("strumento", "Taratura dello strumento scaduta alla data delle prove."))
    if not (dati.get("esecutore") and dati.get("data")):
        anomalie.append(Anomalia("prove", "Indicare chi ha eseguito le prove e quando."))
    return anomalie


def _copia_verifiche_elettriche(sorgente, revisione):
    """La nuova revisione riparte dalle verifiche della precedente, in bozza."""
    for v in sorgente.verifiche_elettriche.all():
        VerificaElettrica.objects.create(
            revisione=revisione, ordine=v.ordine, quadro=v.quadro, dati=v.dati,
            da_eseguire=v.da_eseguire, non_ok=v.non_ok, isolamento_non_ok=v.isolamento_non_ok,
        )


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
            ValidazioneSicurezza.objects.filter(revisione=revisione).delete()
            VerificaElettrica.objects.filter(revisione=revisione).delete()
            ValutazioneFunzione.objects.filter(funzione__revisione=revisione).delete()
            revisione.funzioni.all().delete()
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
    chiavi = set()
    for funzione in revisione.funzioni.select_related("valutazione"):
        nome = f"Funzione di sicurezza «{funzione.nome}»"
        if not funzione.plr:
            anomalie.append(Anomalia("funzione", f"{nome}: completare S, F e P per il PLr."))
        valutazione = getattr(funzione, "valutazione", None)
        if valutazione is None:
            anomalie.append(Anomalia("calcolo", f"{nome}: PL non ancora calcolato."))
            continue
        if valutazione.esito is False:
            pl = f"PL {valutazione.pl}" if valutazione.pl else "PL non calcolabile"
            anomalie.append(Anomalia("calcolo", f"{nome}: {pl}, requisito PLr {funzione.plr or '–'} non dimostrato."))
        elif valutazione.esito is None and funzione.plr:
            anomalie.append(Anomalia("calcolo", f"{nome}: confronto con il PLr da rifare (apri e salva il calcolo)."))
        chiavi |= {
            c.get("articoloId") for ss in valutazione.dettaglio.get("sottosistemi", []) for c in ss.get("componenti", [])
        }
    for verifica in revisione.verifiche_elettriche.filter(isolamento_non_ok__gt=0):
        anomalie.append(Anomalia(
            "elettriche", f"Verifica elettrica «{verifica.quadro}»: isolamento non OK su {verifica.isolamento_non_ok} cavi."
        ))
    da_verificare = list(
        ArticoloSicurezza.objects.filter(chiave__in=chiavi - {None, ""}, verificato=False).values_list("codice", flat=True)
    )
    if da_verificare:
        elenco = ", ".join(sorted(da_verificare)[:10]) + (" …" if len(da_verificare) > 10 else "")
        anomalie.append(Anomalia(
            "articoli", f"{len(da_verificare)} articoli di sicurezza usati nei calcoli sono ancora da verificare: {elenco}."
        ))
    return anomalie
