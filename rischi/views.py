from itertools import groupby

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import servizi
from . import documenti
from .forms import (
    ApplicabilitaFormSet,
    MacchinaForm,
    MisureFormSet,
    ModuliMacchinaForm,
    NuovaCommessaForm,
    SchedaForm,
)
from .models import Analisi, Cliente, Commessa, DocumentoGenerato, Macchina, RegistroModifica, Revisione, SchedaAnalisi


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
    }
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
        {"form": form, "misure": misure, "scheda": scheda, "revisione": revisione, "modificabile": modificabile},
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
    form_moduli = ModuliMacchinaForm(request.POST or None, initial={"moduli": macchina.moduli.all()})
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
                        macchina, form_moduli.cleaned_data["moduli"], request.user
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
                        f"{rimaste} schede dei moduli tolti erano già decise e restano nell'analisi: scartale se non servono.",
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
    return FileResponse(documento.file.open("rb"), as_attachment=True, filename=documento.file.name.rsplit("/", 1)[-1])
