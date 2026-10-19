import json

from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.contrib.auth import admin as _admin_utenti  # noqa: F401 (registra Gruppi prima di aggiungere Duplica)
from django.contrib.auth.models import Group
from django.db import models
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from . import models as m
from .articoli import importa as importa_articoli
from .duplica import duplica
from .servizi import _componenti, importa_funzioni_tipo
from .forms import (
    CAMPI_CONSIDERAZIONI,
    CAMPI_NORME,
    VALORI_AV,
    VALORI_FR,
    VALORI_PR,
    VALORI_SE,
    MisuraForm,
    NormeSchedaMixin,
    _campo_norma,
    campi_norme,
    campo_norme_automatiche,
    _scelta,
    descrivi_fattori,
)
from .testo import in_html


class SoloVistaCollegati:
    """Nei campi collegati della scheda modello resta solo l'occhio per vedere la voce: niente aggiungi,
    modifica o elimina (le voci si gestiscono dai loro elenchi in Libreria e utenti)."""

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        campo = super().formfield_for_dbfield(db_field, request, **kwargs)
        widget = getattr(campo, "widget", None)
        if isinstance(widget, RelatedFieldWidgetWrapper):
            widget.can_add_related = widget.can_change_related = widget.can_delete_related = False
        return campo


class OrdinabileAdmin(admin.ModelAdmin):
    """Ordine delle voci con i pulsanti ↑ e ↓ nell'elenco al posto del numero: la voce scambia il posto con
    quella vicina e tutte le voci si rinumerano 10, 20, 30…; le voci nuove vanno in fondo."""

    exclude = ("ordine",)
    sortable_by = ()  # l'elenco resta nell'ordine scelto con le frecce

    def get_list_display(self, request):
        return (*super().get_list_display(request), "sposta")

    def get_urls(self):
        info = self.opts.app_label, self.opts.model_name
        return [
            path("<int:pk>/sposta/<str:verso>/", self.admin_site.admin_view(self.sposta_voce),
                 name="%s_%s_sposta" % info),
            *super().get_urls(),
        ]

    @admin.display(description="ordine")
    def sposta(self, obj):
        # Pulsanti del modulo dell'elenco (che ha già il token CSRF) inviati all'indirizzo dello spostamento
        nome = f"admin:{self.opts.app_label}_{self.opts.model_name}_sposta"
        return format_html(
            '<span style="white-space:nowrap">'
            '<button type="submit" class="button" formaction="{}" formnovalidate title="Sposta in su" '
            'style="padding:2px 8px;margin-right:4px">↑</button>'
            '<button type="submit" class="button" formaction="{}" formnovalidate title="Sposta in giù" '
            'style="padding:2px 8px">↓</button></span>',
            reverse(nome, args=[obj.pk, "su"]), reverse(nome, args=[obj.pk, "giu"]),
        )

    def sposta_voce(self, request, pk, verso):
        indietro = request.META.get("HTTP_REFERER") or reverse(
            f"admin:{self.opts.app_label}_{self.opts.model_name}_changelist")
        if request.method != "POST" or not self.has_change_permission(request):
            return redirect(indietro)
        voce = get_object_or_404(self.model, pk=pk)
        voci = list(self.model.objects.all())  # nell'ordine del modello (ordine, poi nome o numero)
        i = voci.index(voce)
        j = i - 1 if verso == "su" else i + 1
        if 0 <= j < len(voci):
            voci[i], voci[j] = voci[j], voci[i]
        for numero, v in enumerate(voci, start=1):
            if v.ordine != numero * 10:
                v.ordine = numero * 10
                v.save(update_fields=["ordine"])
        return redirect(indietro)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.ordine = (self.model.objects.aggregate(Max("ordine"))["ordine__max"] or 0) + 10
        super().save_model(request, obj, form, change)


class MisuraModelloInline(SoloVistaCollegati, admin.StackedInline):
    model = m.MisuraModello
    form = MisuraForm
    extra = 0
    # Le norme della scheda stanno nella sezione 1 (anche quelle dei pericoli e delle soluzioni): niente norma
    # per misura. Niente ordine: le misure si numerano da sole (Misura 1, 2, 3…) nell'ordine in cui compaiono.
    fields = ("soluzione", "tipo", "testo")
    template = "admin/rischi/schedamodello/misure_stacked.html"
    sezione = 6
    verbose_name_plural = "Misure di protezione"


class AllegatoModelloInline(admin.StackedInline):
    """Sezione 9: immagini e PDF allegati alla scheda modello, nell'ordine in cui compaiono, con la posizione
    dell'immagine nella pagina e il testo collegato (sopra, sotto o di fianco)."""

    model = m.AllegatoModello
    extra = 1
    fields = (("anteprima", "file"), ("allineamento", "posizione_testo"), "testo")
    readonly_fields = ("anteprima",)
    formfield_overrides = {models.TextField: {"widget": forms.Textarea(attrs={"rows": 3})}}
    verbose_name = "allegato"
    verbose_name_plural = "Immagini allegate"
    sezione = 9

    @admin.display(description="anteprima")
    def anteprima(self, obj):
        if not (obj and obj.pk and obj.file):
            return "–"
        if obj.e_immagine:
            return format_html('<a href="{0}" target="_blank"><img src="{0}" class="anteprima-allegato" alt=""></a>',
                               obj.file.url)
        return format_html('<a href="{}" target="_blank">PDF: {}</a>', obj.file.url, obj.nome_file)


GRUPPI_PERICOLI = {
    "1": "Pericoli meccanici", "2": "Pericoli elettrici", "3": "Pericoli termici", "4": "Rumore",
    "5": "Vibrazioni", "6": "Radiazioni", "7": "Materiali e sostanze", "8": "Ergonomia",
    "9": "Ambiente di utilizzo", "10": "Combinazioni di pericoli",
}


def pericoli_per_gruppo():
    """Pericoli divisi per gruppo (il primo numero del codice, EN ISO 12100 tabella B.1), in ordine di codice."""
    gruppi = {}
    pericoli = sorted(m.Pericolo.objects.all(), key=lambda p: m.ordine_codice(p.codice))
    for pericolo in pericoli:
        numero = pericolo.codice.split(".")[0]
        gruppi.setdefault(numero, []).append((pericolo.pk, str(pericolo)))
    return [(f"{numero}. {GRUPPI_PERICOLI.get(numero, 'Altri pericoli')}", voci) for numero, voci in gruppi.items()]


class SchedaModelloForm(NormeSchedaMixin, forms.ModelForm):
    se_iniziale = _scelta(VALORI_SE)
    fr_iniziale = _scelta(VALORI_FR)
    pr_iniziale = _scelta(VALORI_PR)
    av_iniziale = _scelta(VALORI_AV)
    se_finale = _scelta(VALORI_SE)
    fr_finale = _scelta(VALORI_FR)
    pr_finale = _scelta(VALORI_PR)
    av_finale = _scelta(VALORI_AV)
    locals().update(campi_norme())  # norma_1 … norma_20
    norme_automatiche = campo_norme_automatiche()

    class Meta:
        model = m.SchedaModello
        exclude = ("codice",)
        widgets = {
            "condizioni": forms.CheckboxSelectMultiple,
            "soggetti": forms.CheckboxSelectMultiple,
            "pericoli": forms.CheckboxSelectMultiple(attrs={"class": "scelta-pericoli"}),
            **{campo: forms.Textarea(attrs={"rows": 3, "cols": 80}) for campo in CAMPI_CONSIDERAZIONI},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        descrivi_fattori(self.fields, m.MetodoStima.corrente())
        self._prepara_norme()
        if "pericoli" in self.fields:
            self.fields["pericoli"].choices = pericoli_per_gruppo()

    def clean(self):
        dati = super().clean()
        modulo = dati.get("modulo")
        if modulo and not modulo.sigla:
            self.add_error("modulo", f"Il modulo \"{modulo}\" non ha la sigla: impostala nella pagina del modulo.")
        return dati


@admin.register(m.SchedaModello)
class SchedaModelloAdmin(SoloVistaCollegati, admin.ModelAdmin):
    form = SchedaModelloForm
    list_display = ("codice", "modulo", "requisito", "zona_impianto", "stato")
    list_filter = ("modulo", ("requisito", admin.RelatedOnlyFieldListFilter), "zona_impianto", "stato")
    search_fields = ("codice", "requisito__codice", "requisito__titolo", "testo_istruzioni")
    readonly_fields = ("codice", "note_requisito", "calcolo_iniziale", "calcolo_finale")
    inlines = [MisuraModelloInline, AllegatoModelloInline]

    class Media:
        css = {"all": ("rischi/admin_scheda.css",)}
        js = ("rischi/scheda.js",)
    # Sezioni in sequenza EN ISO 12100, come la scheda nell'analisi; le misure di protezione stanno
    # in fondo alla sezione 6, dopo le considerazioni (vedi admin/rischi/schedamodello/change_form.html).
    fieldsets = (
        ("1. IDENTIFICAZIONE SCHEDA MODELLO", {
            "fields": ("codice", "modulo", "requisito", "stato", "note_requisito", "stampa_note_requisito", "note",
                       *CAMPI_NORME, "norme_automatiche"),
        }),
        ("2. IDENTIFICAZIONE DEL PERICOLO (RESS 1.1.1 a)", {
            "fields": ("considerazioni_pericoli", "pericoli"),
        }),
        ("3. IDENTIFICAZIONE DELLA ZONA PERICOLOSA (RESS 1.1.1 b)", {
            "fields": ("zona_impianto", "zona_pericolosa", "considerazioni_limiti", "condizioni"),
        }),
        ("4. IDENTIFICAZIONE DEI SOGGETTI ESPOSTI (RESS 1.1.1 c, d)", {
            "fields": ("considerazioni_soggetti", "soggetti"),
        }),
        ("5. STIMA INIZIALE DEL RISCHIO (RESS 1.1.1 e)", {
            "fields": (("se_iniziale", "fr_iniziale", "pr_iniziale", "av_iniziale"), "calcolo_iniziale",
                       "considerazioni_stima_iniziale"),
        }),
        # Apre la sezione 6; le misure seguono subito dopo, senza titolo proprio (vedi change_form.html)
        ("6. RIDUZIONE DEL RISCHIO (RESS 1.1.1 f, g)", {
            "fields": ("considerazioni_riduzione",),
        }),
        ("7. STIMA FINALE DEL RISCHIO (RESS 1.1.1 e)", {
            "fields": (("se_finale", "fr_finale", "pr_finale", "av_finale"), "calcolo_finale",
                       "considerazioni_stima_finale"),
        }),
        ("8. VALUTAZIONE DEL RISCHIO RESIDUO", {
            "fields": ("testo_istruzioni",),
        }),
        # Solo titolo: gli allegati sono la riga AllegatoModelloInline (vedi sezione.html)
        ("9. IMMAGINI ALLEGATE", {
            "fields": (),
            "description": "Immagini (JPG, PNG, GIF, BMP) e PDF. Nella valutazione dei rischi le immagini si "
            "stampano nella scheda, i PDF in appendice al documento. Passano alle schede delle commesse.",
        }),
    )

    COLORI_ESITO = {"OK": ("#e6f4ea", "#1e7b34"), "SUGGERITE": ("#fff4e0", "#9a5b00"), "RICHIESTE": ("#fde8e8", "#b42318")}

    def _calcolo(self, se, fr, pr, av, cl):
        """Cl = Fr + Pr + Av con l'esito della matrice del metodo in uso, come nella scheda dell'analisi."""
        if cl is None:
            return "Cl = Fr + Pr + Av = – (compila Fr, Pr e Av e salva)"
        metodo = m.MetodoStima.corrente()
        esito = metodo.esito(se, cl) if metodo else None
        if esito is None:
            return format_html("Cl = {} + {} + {} = <b>{}</b> · esito: –", fr, pr, av, cl)
        sfondo, colore = self.COLORI_ESITO[esito]
        return format_html(
            'Cl = {} + {} + {} = <b>{}</b> · esito: <span style="background:{};color:{};padding:1px 8px;'
            'border-radius:10px;font-weight:600">{}</span>',
            fr, pr, av, cl, sfondo, colore, m.Esito(esito).label,
        )

    @admin.display(description="Note")
    def note_requisito(self, obj):
        """Testo del requisito RESS (Allegato III), si modifica dalla pagina del requisito."""
        if not obj.requisito_id:
            return "Scegli il requisito e salva: qui compare il testo del requisito."
        return format_html('<div class="note-requisito">{}</div>', mark_safe(in_html(obj.requisito.descrizione) or "–"))

    @admin.display(description="Classe ed esito iniziale")
    def calcolo_iniziale(self, obj):
        return self._calcolo(obj.se_iniziale, obj.fr_iniziale, obj.pr_iniziale, obj.av_iniziale, obj.cl_iniziale)

    @admin.display(description="Classe ed esito finale")
    def calcolo_finale(self, obj):
        return self._calcolo(obj.se_finale, obj.fr_finale, obj.pr_finale, obj.av_finale, obj.cl_finale)

    def save_model(self, request, obj, form, change):
        """Codice automatico: alla creazione e quando cambiano modulo o requisito."""
        vecchio = obj.codice
        if not change:
            obj.codice = ""
        elif "modulo" in form.changed_data:
            obj.codice = m.SchedaModello.prossimo_codice(obj.modulo, escludi=obj.pk)
        super().save_model(request, obj, form, change)
        if change and obj.codice != vecchio:
            messages.info(request, f"Codice aggiornato da {vecchio} a {obj.codice} (modulo cambiato).")
        elif not change:
            messages.info(request, f"Codice assegnato: {obj.codice}.")

    def save_formset(self, request, form, formset, change):
        """Le misure prendono il numero progressivo (1, 2, 3…) nell'ordine in cui compaiono nella pagina."""
        super().save_formset(request, form, formset, change)
        if formset.model not in (m.MisuraModello, m.AllegatoModello):
            return
        restanti = [f.instance for f in formset.forms if f.instance.pk and f not in formset.deleted_forms]
        for numero, misura in enumerate(restanti, start=1):
            if misura.ordine != numero:
                misura.ordine = numero
                misura.save(update_fields=["ordine"])


class ModuloForm(forms.ModelForm):
    class Meta:
        model = m.Modulo
        fields = "__all__"

    def clean_sigla(self):
        sigla = self.cleaned_data["sigla"].strip().upper()
        if sigla and m.Modulo.objects.filter(sigla=sigla).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"La sigla {sigla} è già usata da un altro modulo.")
        if self.instance.pk and not sigla and self.instance.schede.exists():
            raise forms.ValidationError("Il modulo ha schede: la sigla non può restare vuota.")
        return sigla


@admin.register(m.Modulo)
class ModuloAdmin(OrdinabileAdmin):
    form = ModuloForm
    list_display = ("nome", "sigla", "condizione", "sempre_attivo", "numero_schede", "attivo")
    readonly_fields = ("elenco_schede",)

    def save_model(self, request, obj, form, change):
        """Cambiando la sigla, le schede modello del modulo prendono la nuova sigla e tengono il numero."""
        vecchia = m.Modulo.objects.get(pk=obj.pk).sigla if change else ""
        super().save_model(request, obj, form, change)
        if change and obj.sigla != vecchia:
            rinominate = obj.allinea_codici_schede()
            messages.info(
                request, f"Sigla cambiata da {vecchia or '–'} a {obj.sigla}: aggiornati i codici di {rinominate} schede modello."
            )

    @admin.display(description="schede del modulo")
    def elenco_schede(self, obj):
        """Sola lettura: una scheda si sposta cambiando il modulo dalla sua pagina."""
        schede = obj.schede.select_related("requisito") if obj.pk else []
        righe = [format_html("<li>{} – {} {}</li>", s.codice, s.requisito.codice, s.requisito.titolo) for s in schede]
        return format_html("<ul style='margin:0;padding-left:1.2em'>{}</ul>", mark_safe("".join(righe))) if righe else "–"

    @admin.display(description="schede")
    def numero_schede(self, obj):
        return obj.schede.count()


NUMERO_NORME_PERICOLO = 10
CAMPI_NORME_PERICOLO = tuple(f"norma_{i}" for i in range(1, NUMERO_NORME_PERICOLO + 1))


class DieciNormeForm(forms.ModelForm):
    """Fino a 10 norme collegate (campo molti-a-molti `norme`), una per selezione."""

    locals().update({nome: _campo_norma(i) for i, nome in enumerate(CAMPI_NORME_PERICOLO, start=1)})

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attuali = list(self.instance.norme.order_by("codice")) if self.instance.pk else []
        for campo, norma in zip(CAMPI_NORME_PERICOLO, attuali):
            self.initial[campo] = norma.pk

    def _save_m2m(self):
        super()._save_m2m()
        scelte = [self.cleaned_data.get(campo) for campo in CAMPI_NORME_PERICOLO]
        self.instance.norme.set(list(dict.fromkeys(n for n in scelte if n)))


class ElencoNorme:
    @admin.display(description="norme")
    def elenco_norme(self, obj):
        return ", ".join(n.codice for n in obj.norme.all()) or "–"


class RequisitoForm(DieciNormeForm):
    class Meta:
        model = m.RequisitoRESS
        fields = ["riferimento", "codice", "titolo", "descrizione"]


@admin.register(m.RequisitoRESS)
class RequisitoAdmin(SoloVistaCollegati, ElencoNorme, admin.ModelAdmin):
    form = RequisitoForm
    list_display = ("codice", "titolo", "riferimento", "elenco_norme")
    list_filter = ("riferimento",)
    search_fields = ("codice", "titolo", "descrizione")
    fields = ("riferimento", "codice", "titolo", "descrizione", *CAMPI_NORME_PERICOLO)

    class Media:
        css = {"all": ("rischi/admin_scheda.css",)}
        js = ("rischi/scheda.js",)


@admin.register(m.Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ("codice", "tipo", "edizione_citata", "edizione_vigente", "armonizzata", "sempre_applicata")
    list_filter = ("tipo", "armonizzata", "sempre_applicata")
    search_fields = ("codice", "titolo")


class ArticoliUtilizzatiFilter(admin.SimpleListFilter):
    """Articoli presenti oggi nei calcoli del PL: funzioni delle commesse e funzioni tipo della libreria."""

    title = "utilizzati nei calcoli"
    parameter_name = "utilizzati"

    def lookups(self, request, model_admin):
        return (("si", "Sì"), ("no", "No"))

    def queryset(self, request, queryset):
        if self.value() not in ("si", "no"):
            return queryset
        chiavi = set()
        for dettaglio in [*m.ValutazioneFunzione.objects.values_list("dettaglio", flat=True),
                          *m.FunzioneTipo.objects.values_list("dettaglio", flat=True)]:
            if isinstance(dettaglio, dict):
                chiavi |= _componenti(dettaglio)
        if self.value() == "si":
            return queryset.filter(chiave__in=chiavi)
        return queryset.exclude(chiave__in=chiavi)


@admin.register(m.ArticoloSicurezza)
class ArticoloSicurezzaAdmin(admin.ModelAdmin):
    list_display = ("codice", "produttore", "tipo", "pfh", "b10d", "mttfd", "verificato", "utilizzato")
    list_filter = (ArticoliUtilizzatiFilter, "produttore", "tipo", "verificato", "libreria")
    search_fields = ("codice", "descrizione", "produttore", "gruppo")
    readonly_fields = ("chiave",)
    fieldsets = (
        (None, {"fields": ("chiave", "codice", "descrizione", "produttore", "tipo", "libreria", "gruppo")}),
        ("Valori", {"fields": ("pfh", "b10d", "mttfd", "pl_max", "fonte", "data_fonte", "verificato")}),
        (None, {"fields": ("utilizzato", "note")}),
    )

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields if obj else ()

    def get_urls(self):
        return [
            path("importa/", self.admin_site.admin_view(self.importa_libreria), name="rischi_articolosicurezza_importa"),
            *super().get_urls(),
        ]

    def importa_libreria(self, request):
        """Librerie dei costruttori (SISTEMA .slb, VDMA 66413 .xml o .zip) o archivio JSON della safety evaluation.
        Il file si legge nel browser con sistema.js, vdma.js e zip.js; al server arriva l'elenco degli articoli."""
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            file = request.FILES.get("articoli")
            try:
                dati = json.loads(file.read().decode("utf-8")) if file else None
                esito = importa_articoli(dati)
            except (ValueError, UnicodeDecodeError) as errore:  # JSON, ArchivioNonValido, valori non numerici
                return JsonResponse({"errore": f"Articoli non importati: {errore}"}, status=400)
            return JsonResponse({"messaggio": f"Articoli di sicurezza: {esito}."})
        contesto = {**self.admin_site.each_context(request), "opts": self.opts, "title": "Importa articoli di sicurezza"}
        return TemplateResponse(request, "admin/rischi/articolosicurezza/importa.html", contesto)


@admin.register(m.FunzioneTipo)
class FunzioneTipoAdmin(admin.ModelAdmin):
    """Funzione tipo compilata come la funzione in commessa: S, F, P con il grafo del rischio, schema a blocchi e
    componenti con il calcolo del PL (stessa pagina della commessa). Si importano anche dalla safety evaluation."""

    list_display = ("nome", "modulo", "parametri", "componenti", "attiva")
    list_filter = ("attiva", "modulo")
    search_fields = ("nome", "descrizione")
    fieldsets = (
        ("1. Funzione", {"fields": ("nome", "descrizione", "modulo")}),
        ("2. PLr dal grafo del rischio (EN ISO 13849-1, allegato A)", {"fields": (("s", "f", "p"), "grafo_rischio")}),
        ("3. Calcolo del PL (EN ISO 13849-1)", {"fields": ("calcolo_pl", "schema")}),
        ("Libreria", {"fields": ("note", "attiva", "ordine")}),
    )
    readonly_fields = ("grafo_rischio", "calcolo_pl", "schema")

    class Media:
        js = ("rischi/grafo.js",)

    def get_urls(self):
        return [
            path("importa/", self.admin_site.admin_view(self.importa), name="rischi_funzionetipo_importa"),
            *super().get_urls(),
        ]

    def importa(self, request):
        """Valutazione esportata dalla safety evaluation ("Esporta valutazione", .json): funzioni tipo e articoli."""
        if not (self.has_add_permission(request) and self.has_change_permission(request)):
            raise PermissionDenied
        if request.method == "POST":
            file = request.FILES.get("file")
            try:
                if file is None:
                    raise ValidationError("Scegli il file .json esportato dalla safety evaluation.")
                try:
                    dati = json.loads(file.read().decode("utf-8-sig"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise ValidationError(f"{file.name} non è un file JSON leggibile.")
                messages.success(request, importa_funzioni_tipo(dati, request.user))
                return redirect("admin:rischi_funzionetipo_changelist")
            except ValidationError as errore:
                messages.error(request, "; ".join(errore.messages))
        contesto = {**self.admin_site.each_context(request), "opts": self.opts, "title": "Importa dalla safety evaluation"}
        return TemplateResponse(request, "admin/rischi/funzionetipo/importa.html", contesto)

    @admin.display(description="grafo del rischio")
    def grafo_rischio(self, obj):
        from .grafico_pl import svg_grafo

        return format_html('<p>PLr: <strong id="plr">{}</strong></p><div class="grafo">{}</div>',
                           obj.plr or "–", mark_safe(svg_grafo(obj.s, obj.f, obj.p)))

    @admin.display(description="PL raggiunto")
    def calcolo_pl(self, obj):
        if not obj.pk:
            return "Salva la funzione tipo, poi compila schema a blocchi e componenti con il calcolo del PL."
        from . import calcolo, grafico_pl

        pulsante = format_html('<p><a class="button" href="{}">Apri il calcolo del PL</a> '
                               '<span class="help">schema a blocchi, componenti, calcolo e verifica PL ≥ PLr, come nella commessa</span></p>',
                               reverse("valutazione_funzione_tipo", args=[obj.pk]))
        if not obj.dettaglio.get("sottosistemi"):
            return format_html("<p>Schema a blocchi e componenti non ancora compilati.</p>{}", pulsante)
        try:
            r = calcolo.calcola(obj, obj.dettaglio)
        except calcolo.CalcoloNonRiuscito as errore:
            return format_html("<p>PL non calcolato qui ({}).</p>{}", errore, pulsante)
        esito = "requisito soddisfatto" if r["ok"] else "requisito non dimostrato"
        grafico = grafico_pl.svg(r.get("pl"), r.get("pfh"), obj.plr, r.get("percorsi") or [], r.get("sottosistemi") or [])
        return format_html("<p><strong>PL {}</strong>{} · {}</p><div class='grafico'>{}</div>{}", r.get("pl") or "non calcolabile",
                           f" (PLr {obj.plr})" if obj.plr else "", esito, mark_safe(grafico), pulsante)

    @admin.display(description="S F P")
    def parametri(self, obj):
        return f"{obj.s or '–'} {obj.f or '–'} {obj.p or '–'}" + (f" · PLr {obj.plr}" if obj.plr else "")

    @admin.display(description="componenti")
    def componenti(self, obj):
        return sum(len(ss.get("componenti") or []) for ss in obj.dettaglio.get("sottosistemi") or [])

    @admin.display(description="sottosistemi e componenti")
    def schema(self, obj):
        """Sottosistemi e articoli della funzione tipo: si cambiano con il calcolo del PL."""
        sottosistemi = obj.dettaglio.get("sottosistemi") or []
        if not sottosistemi:
            return "Nessuno."
        articoli = {a.chiave: a for a in m.ArticoloSicurezza.objects.filter(
            chiave__in={c.get("articoloId") for ss in sottosistemi for c in ss.get("componenti") or []})}
        righe = []
        for ss in sottosistemi:
            nomi = [str(articoli.get(c.get("articoloId"), "articolo non in libreria")) for c in ss.get("componenti") or []]
            percorso = f" · percorso {ss['percorso']}" if (ss.get("percorso") or "").strip() else ""
            categoria = f"cat. {ss['categoria']}" if ss.get("metodo") == "arch" else "PFH da certificato"
            righe.append(format_html("<li><strong>{}</strong> ({}, {}{}): {}</li>", ss.get("nome") or "–", ss.get("ruolo") or "–",
                                     categoria, percorso, ", ".join(nomi) or "nessun articolo"))
        return format_html("<ul style='margin:0;padding-left:16px'>{}</ul>", mark_safe("".join(righe)))


class ScalaInline(admin.TabularInline):
    model = m.ScalaFattore
    extra = 0


class FasciaInline(admin.TabularInline):
    model = m.FasciaClasse
    extra = 0


class CellaInline(admin.TabularInline):
    model = m.CellaMatrice
    extra = 0


@admin.register(m.MetodoStima)
class MetodoAdmin(admin.ModelAdmin):
    list_display = ("versione", "attivo")
    inlines = [FasciaInline, CellaInline, ScalaInline]


@admin.register(m.RegistroModifica)
class RegistroAdmin(admin.ModelAdmin):
    list_display = ("quando", "utente", "azione", "tabella", "descrizione")
    list_filter = ("azione", "tabella")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for modello in (m.RiferimentoNormativo, m.Cliente, m.Fabbricante, m.LegislazioneUE):
    admin.site.register(modello)


class PericoloForm(DieciNormeForm):
    class Meta:
        model = m.Pericolo
        fields = ["codice", "descrizione"]


@admin.register(m.Pericolo)
class PericoloAdmin(admin.ModelAdmin):
    form = PericoloForm
    list_display = ("codice", "descrizione", "elenco_norme")
    search_fields = ("codice", "descrizione", "norme__codice")
    fields = ("codice", "descrizione", *CAMPI_NORME_PERICOLO)

    class Media:
        css = {"all": ("rischi/admin_scheda.css",)}
        js = ("rischi/scheda.js",)

    @admin.display(description="norme")
    def elenco_norme(self, obj):
        return ", ".join(n.codice for n in obj.norme.all()) or "–"


class SoluzioneForm(DieciNormeForm):
    class Meta:
        model = m.SoluzioneProtezione
        fields = ["nome", "tipo", "testo", "parole_chiave"]


@admin.register(m.SoluzioneProtezione)
class SoluzioneProtezioneAdmin(admin.ModelAdmin):
    form = SoluzioneForm
    list_display = ("nome", "tipo", "elenco_norme")
    list_filter = ("tipo",)
    search_fields = ("nome", "testo", "norme__codice")
    fields = ("nome", "tipo", "testo", "parole_chiave", *CAMPI_NORME_PERICOLO)

    class Media:
        css = {"all": ("rischi/admin_scheda.css",)}
        js = ("rischi/scheda.js",)

    @admin.display(description="norme")
    def elenco_norme(self, obj):
        return ", ".join(n.codice for n in obj.norme.all()) or "–"


@admin.register(m.CapitoloValutazione)
class CapitoloValutazioneAdmin(OrdinabileAdmin):
    """Capitoli di testo stampati nella valutazione dei rischi dopo la copertina, nell'ordine dell'elenco."""

    list_display = ("titolo", "attivo")
    list_editable = ("attivo",)
    fields = ("titolo", "testo", "attivo")

    class Media:
        css = {"all": ("rischi/admin_scheda.css",)}
        js = ("rischi/scheda.js",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        campo = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "testo":
            campo.widget.attrs["rows"] = 25
        return campo


@admin.register(m.Figura)
class FiguraAdmin(OrdinabileAdmin):
    list_display = ("nome", "tipo")


@admin.register(m.CondizioneOperativa)
class CondizioneOperativaAdmin(OrdinabileAdmin):
    list_display = ("nome",)


class FiguraMacchinaInline(admin.TabularInline):
    model = m.FiguraMacchina
    extra = 0


@admin.register(m.Commessa)
class CommessaAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "anno", "riferimento")
    search_fields = ("numero", "cliente__ragione_sociale")


@admin.register(m.Macchina)
class MacchinaAdmin(admin.ModelAdmin):
    list_display = ("commessa", "denominazione", "modello", "matricola", "tipo")
    inlines = [FiguraMacchinaInline]



# "Duplica" accanto a "Elimina" nel menu Azione di tutti gli elenchi della libreria e dei gruppi
# (non degli utenti: la copia porterebbe con sé la password; non del registro, che è di sola lettura).
for _modello, _admin in admin.site._registry.items():
    if (_modello._meta.app_label == "rischi" and _modello is not m.RegistroModifica) or _modello is Group:
        _admin.actions = [*(_admin.actions or ()), duplica]


# Le voci dell'app sono divise in gruppi: libreria dell'analisi dei rischi, libreria della sicurezza funzionale,
# commesse e dati aziendali. I gruppi restano in cima, prima di "Autenticazione e autorizzazione".
GRUPPI_LIBRERIA = [
    ("Libreria – analisi dei rischi", [
        "Modulo", "SchedaModello", "Pericolo", "RequisitoRESS", "Norma", "SoluzioneProtezione",
        "CondizioneOperativa", "Figura", "MetodoStima", "CapitoloValutazione", "RiferimentoNormativo",
    ]),
    ("Libreria – sicurezza funzionale", ["FunzioneTipo", "ArticoloSicurezza"]),
    ("Commesse e dati aziendali", ["Commessa", "Macchina", "Cliente", "Fabbricante", "LegislazioneUE", "RegistroModifica"]),
]
_elenco_app = admin.site.get_app_list


def _gruppi_libreria(request, app_label=None):
    elenco = []
    for app in _elenco_app(request, app_label):
        if app["app_label"] != "rischi":
            elenco.append(app)
            continue
        modelli = {modello["object_name"]: modello for modello in app["models"]}
        gruppi = []
        for nome, nomi_modelli in GRUPPI_LIBRERIA:
            voci = [modelli.pop(n) for n in nomi_modelli if n in modelli]
            if voci:
                gruppi.append({**app, "name": nome, "models": voci})
        if modelli:  # voci nuove non ancora assegnate a un gruppo
            gruppi.append({**app, "name": "Altro", "models": list(modelli.values())})
        elenco = gruppi + elenco
    # Gruppo evidenziato nella barra laterale: solo quello della voce aperta (i gruppi hanno lo stesso indirizzo)
    for app in elenco:
        app["corrente"] = any(v.get("admin_url") and v["admin_url"] in request.path for v in app["models"])
    return elenco


admin.site.get_app_list = _gruppi_libreria
