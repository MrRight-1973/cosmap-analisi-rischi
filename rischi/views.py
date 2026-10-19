import json
from itertools import groupby

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.core.files.base import ContentFile
from django.http import FileResponse, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from . import servizi
from . import calcolo, documenti
from .forms import (
    AllegatoForm,
    FunzioneForm,
    ApplicabilitaFormSet,
    MacchinaForm,
    MisureFormSet,
    ModuliMacchinaForm,
    NuovaCommessaForm,
    SchedaForm,
)
from .models import (
    AllegatoAnalisi,
    Analisi,
    ArticoloSicurezza,
    Cliente,
    Commessa,
    DocumentoGenerato,
    FunzioneSicurezza,
    FunzioneTipo,
    MisuraAnalisi,
    Modulo,
    Macchina,
    RegistroModifica,
    RequisitoRESS,
    Revisione,
    SchedaAnalisi,
    ValidazioneSicurezza,
    ValutazioneFunzione,
    VerificaElettrica,
)


def _errore(request, eccezione):
    testo = "; ".join(eccezione.messages) if isinstance(eccezione, ValidationError) else str(eccezione)
    messages.error(request, testo)


@login_required
def elenco_commesse(request):
    commesse = Commessa.objects.select_related("cliente").prefetch_related("macchine__analisi__revisioni")
    righe = []
    for commessa in commesse:
        for macchina in commessa.macchine.all():
            analisi = getattr(macchina, "analisi", None)
            righe.append(
                {
                    "commessa": commessa,
                    "macchina": macchina,
                    "analisi": analisi,
                    "revisione": analisi.revisione_corrente if analisi else None,
                }
            )
    return render(request, "rischi/elenco_commesse.html", {"righe": righe})


@login_required
def nuova_commessa(request):
    form = NuovaCommessaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            with transaction.atomic():
                cliente = d["cliente"] or Cliente.objects.create(
                    ragione_sociale=d["nuovo_cliente"].strip(), paese=d["paese_cliente"]
                )
                commessa = Commessa.objects.create(
                    numero=d["numero"],
                    cliente=cliente,
                    anno=d["anno"],
                    descrizione=d["descrizione"],
                    paese_destinazione=d["paese_destinazione"],
                    riferimento=d["riferimento"],
                )
                macchina = Macchina.objects.create(
                    commessa=commessa,
                    denominazione=d["denominazione"],
                    modello=d["modello"],
                    matricola=d["matricola"],
                    anno_costruzione=d["anno_costruzione"],
                    tipo=d["tipo"],
                    materiali=d["materiali"],
                    funzione=d["funzione"],
                )
                macchina.moduli.set(d["moduli"])
                macchina.altre_legislazioni.set(d["altre_legislazioni"])
                if d["origine"] == "COPIA":
                    analisi = servizi.crea_analisi_da_copia(macchina, d["copia_da"], request.user)
                else:
                    analisi = servizi.crea_analisi_da_libreria(macchina, request.user)
        except (PermissionDenied, ValidationError) as e:
            _errore(request, e)
        else:
            messages.success(
                request, f"Analisi creata con {analisi.revisione_corrente.schede.count()} schede proposte."
            )
            return redirect("analisi", pk=analisi.pk)
    return render(request, "rischi/nuova_commessa.html", {"form": form})


@login_required
def analisi(request, pk, numero=None):
    revisioni = Revisione.objects.filter(analisi_id=pk).select_related(
        "analisi__macchina__commessa__cliente", "compilata_da", "verificata_da", "approvata_da", "metodo"
    )
    if not revisioni:
        return redirect("elenco_commesse")
    revisione = get_object_or_404(revisioni, numero=numero) if numero is not None else revisioni[0]
    schede = list(
        revisione.schede.select_related("modulo", "requisito", "revisione__metodo").prefetch_related("misure")
    )
    gruppi = [(modulo, list(elenco)) for modulo, elenco in groupby(schede, key=lambda s: s.modulo)]
    anomalie = servizi.controlli(revisione) if revisione.stato in (Revisione.Stato.BOZZA, Revisione.Stato.IN_VERIFICA) else []
    utente = request.user
    contesto = {
        "revisione": revisione,
        "revisioni": revisioni,
        "analisi": revisione.analisi,
        "gruppi": gruppi,
        "anomalie": anomalie,
        "anomalie_per_scheda": {a.scheda.pk for a in anomalie if a.scheda},
        "conteggi": {
            "totali": len(schede),
            "da_decidere": sum(1 for s in schede if s.decisione == SchedaAnalisi.Decisione.PROPOSTA),
            "scartate": sum(1 for s in schede if s.decisione == SchedaAnalisi.Decisione.SCARTATA),
        },
        "puo": {
            "compilare": servizi.ha_ruolo(utente, servizi.COMPILATORE),
            "verificare": servizi.ha_ruolo(utente, servizi.VERIFICATORE),
            "approvare": servizi.ha_ruolo(utente, servizi.APPROVATORE),
        },
        "ultima": revisione == revisioni[0],
        "puo_eliminare": servizi.puo_eliminare(utente, revisione.analisi.macchina.commessa),
        "commessa_approvata": servizi.ha_revisioni_approvate(revisione.analisi.macchina.commessa),
        "documenti": revisione.documenti.select_related("generato_da")[:20],
        "funzioni": revisione.funzioni.select_related("valutazione", "prove").prefetch_related("misure__scheda"),
        "verifiche_elettriche": revisione.verifiche_elettriche.all(),
    }
    funzioni_tipo = list(servizi.funzioni_tipo_per(revisione.analisi.macchina))
    nomi = {f.nome for f in contesto["funzioni"]}
    contesto["funzioni_tipo"] = funzioni_tipo
    # Proposte: le funzioni tipo dei moduli della macchina che la revisione non ha ancora
    contesto["funzioni_tipo_proposte"] = [t for t in funzioni_tipo if t.modulo_id and t.nome not in nomi]
    contesto["misure_per_funzioni"] = servizi.misure_per_funzioni(revisione) if revisione.modificabile else []
    return render(request, "rischi/analisi.html", contesto)


@login_required
@require_POST
def azione_revisione(request, pk, azione):
    revisione = get_object_or_404(Revisione, pk=pk)
    nota = request.POST.get("nota", "")
    try:
        if azione == "invia":
            servizi.invia_in_verifica(revisione, request.user)
            messages.success(request, "Revisione inviata in verifica.")
        elif azione == "rimanda":
            servizi.rimanda_in_bozza(revisione, request.user, nota)
            messages.success(request, "Revisione rimandata in bozza.")
        elif azione == "verifica":
            servizi.segna_verificata(revisione, request.user)
            messages.success(request, "Revisione verificata: ora può essere approvata.")
        elif azione == "approva":
            servizi.approva(revisione, request.user)
            messages.success(request, "Revisione approvata.")
        elif azione == "nuova":
            nuova = servizi.nuova_revisione(revisione.analisi, request.user, nota)
            messages.success(request, f"Aperta la revisione {nuova.numero}.")
        else:
            raise ValidationError("Azione sconosciuta.")
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
    return redirect("analisi", pk=revisione.analisi_id)


@login_required
@require_POST
def elimina_commessa(request, pk):
    commessa = get_object_or_404(Commessa, pk=pk)
    if request.POST.get("conferma", "").strip() != commessa.numero:
        messages.error(request, f"Per eliminare la commessa scrivi il suo numero: {commessa.numero}.")
        analisi = Analisi.objects.filter(macchina__commessa=commessa).first()
        return redirect("analisi", pk=analisi.pk) if analisi else redirect("elenco_commesse")
    try:
        servizi.elimina_commessa(commessa, request.user)
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
        analisi = Analisi.objects.filter(macchina__commessa=commessa).first()
        return redirect("analisi", pk=analisi.pk) if analisi else redirect("elenco_commesse")
    messages.success(request, f"Commessa {commessa.numero} eliminata.")
    return redirect("elenco_commesse")


def _salva_scheda(request, scheda, revisione, nuova):
    form = SchedaForm(
        request.POST or None, instance=scheda,
        riferimento=revisione.analisi.macchina.commessa.riferimento,
        metodo=revisione.metodo,
    )
    misure = MisureFormSet(request.POST or None, instance=scheda, prefix="misure")
    modificabile = revisione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)
    if not modificabile:
        for campo in form.fields.values():
            campo.disabled = True
    if request.method == "POST":
        if not modificabile:
            raise PermissionDenied("Scheda non modificabile.")
        if form.is_valid() and misure.is_valid():
            try:
                with transaction.atomic():
                    scheda = form.save(commit=False)
                    if nuova:
                        scheda.revisione = revisione
                        scheda.decisione = SchedaAnalisi.Decisione.AGGIUNTA
                    elif "decisione" not in form.changed_data and form.contenuto_cambiato() and scheda.decisione in (
                        SchedaAnalisi.Decisione.PROPOSTA,
                        SchedaAnalisi.Decisione.CONFERMATA,
                    ):
                        scheda.decisione = SchedaAnalisi.Decisione.MODIFICATA
                    if nuova or "decisione" in form.changed_data or form.contenuto_cambiato():
                        scheda.decisa_da = request.user
                        scheda.decisa_il = timezone.now()
                    vecchio_codice = scheda.codice
                    if nuova or "modulo" in form.changed_data:
                        scheda.codice = servizi.codice_scheda(revisione, scheda.modulo, escludi=scheda.pk)
                    scheda.full_clean(exclude=["condizioni", "pericoli", "norme", "soggetti", "revisione"])
                    scheda.save()
                    form.save_m2m()
                    servizi.allinea_figure(revisione.analisi.macchina, revisione)
                    misure.instance = scheda
                    misure.save()
            except ValidationError as e:
                form.add_error(None, e)
            else:
                if nuova:
                    messages.success(request, f"Scheda {scheda.codice} aggiunta.")
                elif scheda.codice != vecchio_codice:
                    messages.success(request, f"Scheda salvata: codice aggiornato da {vecchio_codice} a {scheda.codice}.")
                else:
                    messages.success(request, "Scheda salvata.")
                return redirect("analisi", pk=revisione.analisi_id)
    return render(
        request,
        "rischi/scheda.html",
        {
            "form": form, "misure": misure, "scheda": scheda, "revisione": revisione, "modificabile": modificabile,
            "form_allegato": AllegatoForm(),
        },
    )


@login_required
def scheda(request, pk):
    scheda = get_object_or_404(SchedaAnalisi.objects.select_related("revisione__analisi"), pk=pk)
    return _salva_scheda(request, scheda, scheda.revisione, nuova=False)


@login_required
def nuova_scheda(request, revisione_pk):
    revisione = get_object_or_404(Revisione, pk=revisione_pk)
    return _salva_scheda(request, SchedaAnalisi(revisione=revisione), revisione, nuova=True)


@login_required
@require_POST
def decisione_rapida(request, pk):
    """Conferma con un clic una scheda proposta."""
    scheda = get_object_or_404(SchedaAnalisi, pk=pk)
    try:
        servizi.decidi_scheda(scheda, request.user, SchedaAnalisi.Decisione.CONFERMATA)
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
    return redirect(f"{_url_analisi(scheda)}#scheda-{scheda.pk}")


@login_required
@require_POST
def aggiorna_da_modello(request, pk):
    """Ricarica nella scheda della commessa il contenuto della scheda modello in libreria."""
    scheda = get_object_or_404(SchedaAnalisi.objects.select_related("revisione__analisi"), pk=pk)
    try:
        modello = servizi.aggiorna_da_modello(scheda, request.user)
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
    else:
        messages.success(request, f"Scheda aggiornata con il contenuto della scheda modello {modello.codice}.")
    return redirect("scheda", pk=scheda.pk)


def _scheda_modificabile(request, scheda):
    if not (scheda.revisione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)):
        raise PermissionDenied("Scheda non modificabile.")


@login_required
@require_POST
def aggiungi_allegato(request, pk):
    """Sezione 9 della scheda della commessa: carica un'immagine o un PDF."""
    scheda = get_object_or_404(SchedaAnalisi.objects.select_related("revisione"), pk=pk)
    _scheda_modificabile(request, scheda)
    form = AllegatoForm(request.POST, request.FILES)
    if form.is_valid():
        allegato = form.save(commit=False)
        allegato.scheda = scheda
        allegato.ordine = (scheda.allegati.aggregate(m=Max("ordine"))["m"] or 0) + 1
        allegato.save()
        messages.success(request, f"Allegato caricato: {allegato.nome_file}.")
    else:
        messages.error(request, " ".join(e for errori in form.errors.values() for e in errori))
    return redirect(f"{reverse('scheda', args=[scheda.pk])}#allegati")


@login_required
@require_POST
def elimina_allegato(request, pk):
    allegato = get_object_or_404(AllegatoAnalisi.objects.select_related("scheda__revisione"), pk=pk)
    scheda = allegato.scheda
    _scheda_modificabile(request, scheda)
    # Si toglie solo il collegamento: il file può servire alla scheda modello o ad altre commesse.
    allegato.delete()
    messages.success(request, "Allegato tolto dalla scheda.")
    return redirect(f"{reverse('scheda', args=[scheda.pk])}#allegati")


def _url_analisi(scheda):
    from django.urls import reverse

    return reverse("analisi", kwargs={"pk": scheda.revisione.analisi_id})


@login_required
def applicabilita(request, revisione_pk):
    revisione = get_object_or_404(Revisione, pk=revisione_pk)
    modificabile = revisione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)
    righe = revisione.applicabilita.select_related("requisito")
    formset = ApplicabilitaFormSet(request.POST or None, queryset=righe)
    if request.method == "POST":
        if not modificabile:
            raise PermissionDenied("Revisione non modificabile.")
        if formset.is_valid():
            formset.save()
            messages.success(request, "Applicabilità dei requisiti salvata.")
            return redirect("analisi", pk=revisione.analisi_id)
    schede_per_requisito = {}
    for s in revisione.schede.exclude(decisione=SchedaAnalisi.Decisione.SCARTATA):
        schede_per_requisito[s.requisito_id] = schede_per_requisito.get(s.requisito_id, 0) + 1
    righe_form = [(f, f.instance, schede_per_requisito.get(f.instance.requisito_id, 0)) for f in formset]
    return render(
        request,
        "rischi/applicabilita.html",
        {"formset": formset, "righe": righe_form, "revisione": revisione, "modificabile": modificabile},
    )


def _salva_funzione(request, funzione, revisione):
    modificabile = revisione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)
    iniziali = {}
    suggeriti = False
    if not funzione.pk and request.GET.get("misura", "").isdigit():
        misura = MisuraAnalisi.objects.filter(pk=request.GET["misura"], scheda__revisione=revisione).select_related("scheda").first()
        if misura:
            iniziali["misure"] = [misura.pk]
            iniziali["nome"] = misura.testo.split(".")[0].split(";")[0][:120]
            iniziali["s"], iniziali["f"], iniziali["p"] = servizi.sfp_suggeriti(misura.scheda)
            suggeriti = any((iniziali["s"], iniziali["f"], iniziali["p"]))
    form = FunzioneForm(request.POST or None, instance=funzione, revisione=revisione, initial=iniziali)
    if not modificabile:
        for campo in form.fields.values():
            campo.disabled = True
    if request.method == "POST":
        if not modificabile:
            raise PermissionDenied("Funzione non modificabile.")
        if form.is_valid():
            nuova = not funzione.pk
            with transaction.atomic():
                funzione = form.save(commit=False)
                if nuova:
                    funzione.revisione = revisione
                    funzione.ordine = (revisione.funzioni.aggregate(m=Max("ordine"))["m"] or 0) + 10
                funzione.save()
                form.save_m2m()
                if hasattr(funzione, "valutazione") and {"s", "f", "p"} & set(form.changed_data):
                    servizi.salva_valutazione(funzione, {}, {}, request.user)  # il PLr è cambiato: nuovo confronto
            messages.success(request, f"Funzione «{funzione.nome}» salvata" + (f", PLr {funzione.plr}." if funzione.plr else "."))
            return redirect(f"{reverse('analisi', args=[revisione.analisi_id])}#funzioni")
    schede = {m.scheda for m in funzione.misure.select_related("scheda__revisione__metodo")} if funzione.pk else set()
    grafico = _grafico_pl(funzione) if funzione.pk and hasattr(funzione, "valutazione") else ""
    return render(
        request,
        "rischi/funzione.html",
        {
            "form": form, "funzione": funzione, "revisione": revisione, "modificabile": modificabile,
            "schede": sorted(schede, key=lambda s: s.codice),
            "puo_funzione_tipo": funzione.pk and request.user.has_perm("rischi.add_funzionetipo"),
            "suggeriti": suggeriti,
            "grafico_pl": grafico,
            "moduli_macchina": revisione.analisi.macchina.moduli.filter(attivo=True),
        },
    )


def _grafico_pl(funzione):
    """SVG del PL raggiunto: con il motore di calcolo anche percorsi e sottosistemi, altrimenti solo la funzione."""
    from django.utils.safestring import mark_safe

    from . import calcolo, grafico_pl

    valutazione = funzione.valutazione
    try:
        r = calcolo.calcola(funzione, valutazione.dettaglio)
        return mark_safe(grafico_pl.svg(r.get("pl"), r.get("pfh"), funzione.plr, r.get("percorsi") or [], r.get("sottosistemi") or []))
    except Exception:  # senza Node o con uno schema incompleto resta il risultato salvato
        if valutazione.pfh is None:
            return ""
        return mark_safe(grafico_pl.svg(valutazione.pl, valutazione.pfh, funzione.plr))


@login_required
def funzione(request, pk):
    funzione = get_object_or_404(FunzioneSicurezza.objects.select_related("revisione__analisi"), pk=pk)
    return _salva_funzione(request, funzione, funzione.revisione)


@login_required
def nuova_funzione(request, revisione_pk):
    revisione = get_object_or_404(Revisione, pk=revisione_pk)
    return _salva_funzione(request, FunzioneSicurezza(revisione=revisione), revisione)


def _vai_funzioni(revisione):
    return redirect(reverse("analisi_revisione", args=[revisione.analisi_id, revisione.numero]) + "#funzioni")


@login_required
@require_POST
def aggiungi_funzione_tipo(request, revisione_pk):
    revisione = get_object_or_404(Revisione.objects.select_related("analisi__macchina"), pk=revisione_pk)
    funzione_tipo = get_object_or_404(servizi.funzioni_tipo_per(revisione.analisi.macchina), pk=request.POST.get("funzione_tipo") or 0)
    try:
        funzione = servizi.aggiungi_funzione_tipo(revisione, funzione_tipo, request.user)
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
        return _vai_funzioni(revisione)
    messages.success(request, f"Funzione «{funzione.nome}» aggiunta dalla funzione tipo: collega le misure delle schede.")
    return redirect("funzione", pk=funzione.pk)


@login_required
@require_POST
def importa_safety_evaluation(request, revisione_pk):
    """Valutazione esportata dalla safety evaluation (pulsante "Esporta valutazione", file .json)."""
    revisione = get_object_or_404(Revisione, pk=revisione_pk)
    file = request.FILES.get("file")
    try:
        if file is None:
            raise ValidationError("Scegli il file .json esportato dalla safety evaluation.")
        try:
            dati = json.loads(file.read().decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValidationError(f"{file.name} non è un file JSON leggibile.")
        messages.success(request, servizi.importa_safety_evaluation(revisione, dati, request.user))
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
    return _vai_funzioni(revisione)


@login_required
@require_POST
def salva_come_funzione_tipo(request, pk):
    funzione = get_object_or_404(FunzioneSicurezza.objects.select_related("valutazione"), pk=pk)
    modulo = Modulo.objects.filter(pk=request.POST.get("modulo") or 0).first()
    try:
        tipo = servizi.salva_come_funzione_tipo(funzione, request.POST.get("nome", ""), modulo, request.user)
        messages.success(request, f"Funzione tipo «{tipo.nome}» salvata nella libreria" + (f", modulo {modulo}." if modulo else ", per tutte le macchine."))
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
    return redirect("funzione", pk=funzione.pk)


@login_required
@require_POST
def elimina_funzione(request, pk):
    funzione = get_object_or_404(FunzioneSicurezza.objects.select_related("revisione"), pk=pk)
    revisione = funzione.revisione
    if not (revisione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)):
        raise PermissionDenied("Funzione non modificabile.")
    with transaction.atomic():
        if hasattr(funzione, "valutazione"):
            funzione.valutazione.delete()
        funzione.delete()
    messages.success(request, f"Funzione «{funzione.nome}» eliminata.")
    return redirect(f"{reverse('analisi', args=[revisione.analisi_id])}#funzioni")


@login_required
def valutazione_funzione(request, pk):
    """Calcolo del PL della funzione: la pagina usa engine.js nel browser; al salvataggio il server ricalcola."""
    funzione = get_object_or_404(FunzioneSicurezza.objects.select_related("revisione__analisi__macchina__commessa"), pk=pk)
    revisione = funzione.revisione
    modificabile = revisione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)
    valutazione = getattr(funzione, "valutazione", None)
    if request.method == "POST":
        if not modificabile:
            return JsonResponse({"errore": "La revisione non è in bozza o non hai il ruolo di compilatore."}, status=403)
        try:
            dati = json.loads(request.body)
            dettaglio = dati["dettaglio"]
            if not isinstance(dettaglio, dict) or not isinstance(dettaglio.get("sottosistemi", []), list):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            return JsonResponse({"errore": "Dati della valutazione non validi."}, status=400)
        try:
            risultato = servizi.salva_valutazione(funzione, dettaglio, dati.get("risultato") or {}, request.user)
        except (PermissionDenied, ValidationError) as e:
            return JsonResponse({"errore": "; ".join(getattr(e, "messages", [str(e)]))}, status=400)
        return JsonResponse(risultato)
    contesto = {
        "funzione": funzione, "revisione": revisione, "modificabile": modificabile, "valutazione": valutazione,
        "dati": {
            "dettaglio": valutazione.dettaglio if valutazione else {},
            "nome": funzione.nome, "S": funzione.s or None, "F": funzione.f or None, "P": funzione.p or None,
            "modificabile": modificabile,
            "salva_url": reverse("valutazione_funzione", args=[funzione.pk]),
            "articoli_url": reverse("articoli_sicurezza"),
            "csrf": get_token(request),
        },
    }
    return render(request, "rischi/valutazione.html", contesto)


def _puo(utente):
    return {
        "compilare": servizi.ha_ruolo(utente, servizi.COMPILATORE),
        "verificare": servizi.ha_ruolo(utente, servizi.VERIFICATORE),
        "approvare": servizi.ha_ruolo(utente, servizi.APPROVATORE),
    }


def _json_post(request, chiave):
    try:
        dati = json.loads(request.body)
        valore = dati[chiave]
        if not isinstance(valore, dict):
            raise ValueError
    except (ValueError, KeyError, TypeError):
        raise ValidationError("Dati non validi.")
    return dati


def _risposta_errore(e):
    stato = 403 if isinstance(e, PermissionDenied) else 400
    return JsonResponse({"errore": "; ".join(getattr(e, "messages", [str(e)]))}, status=stato)


@login_required
def validazione(request, pk):
    """Validazione delle funzioni della revisione (EN ISO 13849-2), con flusso proprio: prove per funzione, misure
    contro i guasti sistematici, controlli e relazione PDF."""
    revisione = get_object_or_404(Revisione.objects.select_related("analisi__macchina__commessa"), pk=pk)
    validazione = servizi.validazione_di(revisione)
    modificabile = validazione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)
    if request.method == "POST":
        try:
            dati = _json_post(request, "dati")
            return JsonResponse(servizi.salva_sistematiche(revisione, dati["dati"], request.user))
        except (PermissionDenied, ValidationError) as e:
            return _risposta_errore(e)
    quadro = servizi.quadro_validazione(revisione)
    contesto = {
        "revisione": revisione,
        "analisi": revisione.analisi,
        "validazione": validazione,
        "righe": quadro["righe"],
        "anomalie": quadro["anomalie"],
        "senza_motore": quadro["sistematiche"] is None,
        "modificabile": modificabile,
        "puo": _puo(request.user),
        "documenti": revisione.documenti.filter(tipo=DocumentoGenerato.Tipo.FUNZIONI).select_related("generato_da")[:20],
        "dati": {
            "modo": "sistematiche",
            "sistematiche": validazione.sistematiche,
            "modificabile": modificabile,
            "salva_url": reverse("validazione", args=[revisione.pk]),
            "csrf": get_token(request),
        },
    }
    return render(request, "rischi/validazione.html", contesto)


@login_required
@require_POST
def azione_validazione(request, pk, azione):
    revisione = get_object_or_404(Revisione, pk=pk)
    nota = request.POST.get("nota", "")
    azioni = {
        "invia": (servizi.invia_validazione, "Validazione inviata in verifica."),
        "verifica": (servizi.verifica_validazione, "Validazione verificata: ora può essere approvata."),
        "approva": (servizi.approva_validazione, "Validazione approvata."),
    }
    try:
        if azione == "rimanda":
            servizi.rimanda_validazione(revisione, request.user, nota)
            messages.success(request, "Validazione rimandata in bozza.")
        elif azione in azioni:
            funzione, messaggio = azioni[azione]
            funzione(revisione, request.user)
            messages.success(request, messaggio)
        else:
            raise ValidationError("Azione sconosciuta.")
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
    return redirect("validazione", pk=revisione.pk)


@login_required
def prove_funzione(request, pk):
    """Prove di validazione di una funzione: le prove standard vengono dallo schema a blocchi (validazione.js)."""
    funzione = get_object_or_404(
        FunzioneSicurezza.objects.select_related("revisione__analisi__macchina__commessa"), pk=pk
    )
    revisione = funzione.revisione
    validazione = servizi.validazione_di(revisione)
    modificabile = validazione.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)
    prove = getattr(funzione, "prove", None)
    if request.method == "POST":
        try:
            dati = _json_post(request, "dati")
            prove_pagina = dati.get("prove") if isinstance(dati.get("prove"), list) else []
            return JsonResponse(servizi.salva_prove(funzione, dati["dati"], prove_pagina, request.user))
        except (PermissionDenied, ValidationError) as e:
            return _risposta_errore(e)
    valutazione = getattr(funzione, "valutazione", None)
    contesto = {
        "funzione": funzione, "revisione": revisione, "validazione": validazione, "modificabile": modificabile,
        "valutazione": valutazione,
        "dati": {
            "modo": "prove",
            "nome": funzione.nome,
            "dettaglio": valutazione.dettaglio if valutazione else {},
            "prove": prove.dati if prove else {},
            "modificabile": modificabile,
            "salva_url": reverse("prove_funzione", args=[funzione.pk]),
            "csrf": get_token(request),
        },
    }
    return render(request, "rischi/prove.html", contesto)


@login_required
@require_POST
def nuova_verifica_elettrica(request, pk):
    revisione = get_object_or_404(Revisione, pk=pk)
    try:
        verifica = servizi.nuova_verifica_elettrica(revisione, request.POST.get("quadro", ""), request.user)
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
        return redirect(reverse("analisi_revisione", args=[revisione.analisi_id, revisione.numero]) + "#verifiche-elettriche")
    return redirect("verifica_elettrica", pk=verifica.pk)


@login_required
def verifica_elettrica(request, pk):
    """Verifiche elettriche di un quadro (IEC 60204-1, cap. 18): prove, registro misure, flusso, PDF e modulo."""
    verifica = get_object_or_404(VerificaElettrica.objects.select_related("revisione__analisi__macchina__commessa"), pk=pk)
    revisione = verifica.revisione
    modificabile = verifica.modificabile and servizi.ha_ruolo(request.user, servizi.COMPILATORE)
    if request.method == "POST":
        try:
            dati = _json_post(request, "dati")
            risposta = servizi.salva_verifica_elettrica(
                verifica, dati.get("quadro", ""), dati["dati"], dati.get("risultato") or {}, request.user
            )
            return JsonResponse(risposta)
        except (PermissionDenied, ValidationError) as e:
            return _risposta_errore(e)
    try:
        risultato = calcolo.elettriche(verifica.dati)
    except calcolo.CalcoloNonRiuscito:
        risultato = None
    contesto = {
        "verifica": verifica, "revisione": revisione, "analisi": revisione.analisi, "modificabile": modificabile,
        "puo": _puo(request.user),
        "anomalie": servizi.controlli_verifica_elettrica(verifica, risultato),
        "senza_motore": risultato is None,
        "documenti": verifica.documenti.select_related("generato_da")[:20],
        "dati": {
            "quadro": verifica.quadro, "dati": verifica.dati, "modificabile": modificabile,
            "macchina": str(revisione.analisi.macchina.denominazione),
            "salva_url": reverse("verifica_elettrica", args=[verifica.pk]),
            "modulo_url": reverse("modulo_verifica_elettrica", args=[verifica.pk]),
            "csrf": get_token(request),
        },
    }
    return render(request, "rischi/verifica_elettrica.html", contesto)


@login_required
@require_POST
def azione_verifica_elettrica(request, pk, azione):
    verifica = get_object_or_404(VerificaElettrica.objects.select_related("revisione"), pk=pk)
    azioni = {
        "invia": (servizi.invia_verifica_elettrica, "Verifica inviata in verifica."),
        "verifica": (servizi.segna_verifica_elettrica_verificata, "Verifica controllata: ora può essere approvata."),
        "approva": (servizi.approva_verifica_elettrica, "Verifica elettrica approvata."),
    }
    try:
        if azione == "rimanda":
            servizi.rimanda_verifica_elettrica(verifica, request.user, request.POST.get("nota", ""))
            messages.success(request, "Verifica rimandata in bozza.")
        elif azione == "elimina":
            revisione = verifica.revisione
            servizi.elimina_verifica_elettrica(verifica, request.user)
            messages.success(request, f"Verifica elettrica «{verifica.quadro}» eliminata.")
            return redirect(reverse("analisi_revisione", args=[revisione.analisi_id, revisione.numero]) + "#verifiche-elettriche")
        elif azione in azioni:
            funzione, messaggio = azioni[azione]
            funzione(verifica, request.user)
            messages.success(request, messaggio)
        else:
            raise ValidationError("Azione sconosciuta.")
    except (PermissionDenied, ValidationError) as e:
        _errore(request, e)
    return redirect("verifica_elettrica", pk=verifica.pk)


def _nome_file_verifica(verifica, prefisso, definitivo):
    revisione = verifica.revisione
    numero = revisione.analisi.macchina.commessa.numero.replace("/", "-")
    quadro = slugify(verifica.quadro)[:40] or f"quadro-{verifica.pk}"
    return f"{prefisso}_{numero}_{quadro}_rev{revisione.numero}{'' if definitivo else '_BOZZA'}.pdf"


@login_required
@require_POST
def genera_verifica_elettrica(request, pk):
    verifica = get_object_or_404(VerificaElettrica.objects.select_related("revisione__analisi__macchina__commessa"), pk=pk)
    try:
        contenuto = documenti.verifiche_elettriche(verifica)
    except calcolo.CalcoloNonRiuscito as e:
        messages.error(request, f"Documento non generato: serve il motore di calcolo sul server ({e})")
        return redirect("verifica_elettrica", pk=verifica.pk)
    definitivo = verifica.stato == VerificaElettrica.Stato.APPROVATA
    documento = DocumentoGenerato(
        revisione=verifica.revisione, tipo=DocumentoGenerato.Tipo.ELETTRICHE, verifica_elettrica=verifica,
        definitivo=definitivo, generato_da=request.user,
    )
    documento.file.save(_nome_file_verifica(verifica, "Verifiche_elettriche", definitivo), ContentFile(contenuto), save=True)
    return FileResponse(documento.file.open("rb"), as_attachment=False, filename=documento.file.name.rsplit("/", 1)[-1],
                        content_type="application/pdf")


@login_required
def modulo_verifica_elettrica(request, pk):
    """Modulo rilievi da stampare per i tecnici: non è un documento firmato e non si archivia."""
    verifica = get_object_or_404(VerificaElettrica.objects.select_related("revisione__analisi__macchina__commessa"), pk=pk)
    try:
        contenuto = documenti.modulo_tecnici(verifica)
    except calcolo.CalcoloNonRiuscito as e:
        messages.error(request, f"Modulo non generato: serve il motore di calcolo sul server ({e})")
        return redirect("verifica_elettrica", pk=verifica.pk)
    nome = _nome_file_verifica(verifica, "Modulo_rilievi", True)
    return HttpResponse(contenuto, content_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{nome}"'})


@login_required
def articoli_sicurezza(request):
    """Articoli di sicurezza della libreria nella forma di engine.js, per la pagina del calcolo PL."""
    return JsonResponse({"articoli": [calcolo.articolo_js(a) for a in ArticoloSicurezza.objects.all()]})


@login_required
def registro(request):
    voci = RegistroModifica.objects.select_related("utente")[:300]
    return render(request, "rischi/registro.html", {"voci": voci})


@login_required
def macchina(request, pk):
    macchina = get_object_or_404(Macchina.objects.select_related("commessa"), pk=pk)
    analisi = getattr(macchina, "analisi", None)
    modificabile = servizi.ha_ruolo(request.user, servizi.COMPILATORE) and (
        not analisi or analisi.revisione_corrente.modificabile
    )
    form = MacchinaForm(request.POST or None, instance=macchina)
    riferimento = macchina.commessa.riferimento
    form_moduli = ModuliMacchinaForm(
        request.POST or None,
        riferimento=riferimento,
        initial={
            "moduli": macchina.moduli.all(),
            "schede": servizi.schede_attive_libreria(macchina),
            "requisiti": RequisitoRESS.objects.filter(riferimento=riferimento).exclude(
                codice__in=macchina.requisiti_esclusi.values("codice")
            ),
        },
    )
    if not modificabile:
        campi = list(form.fields.values()) + list(form_moduli.fields.values())
        for campo in campi:
            campo.disabled = True
    if request.method == "POST":
        if not modificabile:
            raise PermissionDenied("Dati della macchina modificabili solo con una revisione in bozza.")
        if form.is_valid() and form_moduli.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    aggiunte, tolte, rimaste = servizi.cambia_moduli(
                        macchina,
                        form_moduli.cleaned_data["moduli"],
                        request.user,
                        form_moduli.escluse(),
                        form_moduli.requisiti_esclusi(),
                    )
            except (PermissionDenied, ValidationError) as e:
                _errore(request, e)
            else:
                messages.success(request, "Dati della macchina salvati.")
                if aggiunte or tolte:
                    messages.info(request, f"Schede aggiunte come proposte: {aggiunte}; schede tolte: {tolte}.")
                if rimaste:
                    messages.warning(
                        request,
                        f"{rimaste} schede tolte erano già decise e restano nell'analisi: scartale se non servono.",
                    )
                return redirect("analisi", pk=analisi.pk) if analisi else redirect("elenco_commesse")
    return render(
        request,
        "rischi/macchina.html",
        {
            "form": form,
            "form_moduli": form_moduli,
            "macchina": macchina,
            "analisi": analisi,
            "modificabile": modificabile,
        },
    )


NOMI_FILE = {
    "DICHIARAZIONE": "Dichiarazione_UE",
    "FUNZIONI": "Relazione_funzioni_sicurezza",
    "VALUTAZIONE": "Valutazione_rischi",
    "RESIDUI": "Rischi_residui",
}


@login_required
@require_POST
def genera_documento(request, pk, tipo):
    revisione = get_object_or_404(Revisione.objects.select_related("analisi__macchina__commessa"), pk=pk)
    tipo = tipo.upper()
    if tipo not in documenti.GENERATORI:
        raise ValidationError("Tipo di documento sconosciuto.")
    lingua = request.POST.get("lingua", "it") if tipo == "DICHIARAZIONE" else "it"
    if lingua not in documenti.TESTI:
        lingua = "it"
    if tipo == "FUNZIONI":
        try:
            contenuto = documenti.genera(tipo, revisione, lingua)
        except calcolo.CalcoloNonRiuscito as e:
            messages.error(request, f"Relazione non generata: serve il motore di calcolo sul server ({e})")
            return redirect("validazione", pk=revisione.pk)
        validazione = getattr(revisione, "validazione", None)
        definitivo = bool(validazione and validazione.stato == ValidazioneSicurezza.Stato.APPROVATA)
    else:
        contenuto = documenti.genera(tipo, revisione, lingua)
        definitivo = revisione.stato == Revisione.Stato.APPROVATA
    numero = revisione.analisi.macchina.commessa.numero.replace("/", "-")
    nome = f"{NOMI_FILE[tipo]}_{numero}_rev{revisione.numero}{'' if definitivo else '_BOZZA'}_{lingua}.pdf"
    documento = DocumentoGenerato(
        revisione=revisione, tipo=tipo, lingua=lingua, definitivo=definitivo, generato_da=request.user
    )
    documento.file.save(nome, ContentFile(contenuto), save=True)
    return FileResponse(documento.file.open("rb"), as_attachment=False, filename=nome, content_type="application/pdf")


@login_required
def scarica_documento(request, pk):
    documento = get_object_or_404(DocumentoGenerato, pk=pk)
    # Si apre nel browser (nuova scheda); da lì si salva o si stampa
    return FileResponse(documento.file.open("rb"), as_attachment=False, filename=documento.file.name.rsplit("/", 1)[-1])
