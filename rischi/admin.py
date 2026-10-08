from django import forms
from django.contrib import admin, messages
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.contrib.auth import admin as _admin_utenti  # noqa: F401 (registra Gruppi prima di aggiungere Duplica)
from django.contrib.auth.models import Group
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from . import models as m
from .duplica import duplica
from .forms import (
    CAMPI_CONSIDERAZIONI,
    CAMPI_NORME,
    VALORI_AV,
    VALORI_FR,
    VALORI_PR,
    VALORI_SE,
    NormeSchedaMixin,
    _campo_norma,
    campi_norme,
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


class MisuraModelloInline(SoloVistaCollegati, admin.StackedInline):
    model = m.MisuraModello
    extra = 0
    # Le norme della scheda stanno nella sezione 1 (anche quelle dei pericoli): niente norma per misura.
    fields = ("ordine", "tipo", "testo")
    verbose_name_plural = "Misure di protezione"


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

    class Meta:
        model = m.SchedaModello
        exclude = ("codice",)
        widgets = {
            "condizioni": forms.CheckboxSelectMultiple,
            "soggetti": forms.CheckboxSelectMultiple,
            **{campo: forms.Textarea(attrs={"rows": 3, "cols": 80}) for campo in CAMPI_CONSIDERAZIONI},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        descrivi_fattori(self.fields, m.MetodoStima.corrente())
        self._prepara_norme()

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
    filter_horizontal = ("pericoli",)
    readonly_fields = ("codice", "note_requisito", "calcolo_iniziale", "calcolo_finale")
    inlines = [MisuraModelloInline]

    class Media:
        css = {"all": ("rischi/admin_scheda.css",)}
        js = ("rischi/scheda.js",)
    # Sezioni in sequenza EN ISO 12100, come la scheda nell'analisi; le misure di protezione stanno
    # in fondo alla sezione 6, dopo le considerazioni (vedi admin/rischi/schedamodello/change_form.html).
    fieldsets = (
        ("1. IDENTIFICAZIONE SCHEDA MODELLO", {
            "fields": ("codice", "modulo", "requisito", "stato", "note_requisito", "stampa_note_requisito", "note",
                       *CAMPI_NORME),
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
class ModuloAdmin(admin.ModelAdmin):
    form = ModuloForm
    list_display = ("nome", "sigla", "condizione", "sempre_attivo", "numero_schede", "attivo", "ordine")
    list_editable = ("ordine",)
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


@admin.register(m.RequisitoRESS)
class RequisitoAdmin(SoloVistaCollegati, admin.ModelAdmin):
    list_display = ("codice", "titolo", "riferimento")
    list_filter = ("riferimento",)
    search_fields = ("codice", "titolo", "descrizione")
    fields = ("riferimento", "codice", "titolo", "descrizione")

    class Media:
        css = {"all": ("rischi/admin_scheda.css",)}
        js = ("rischi/scheda.js",)


@admin.register(m.Norma)
class NormaAdmin(admin.ModelAdmin):
    list_display = ("codice", "tipo", "edizione_citata", "edizione_vigente", "armonizzata")
    list_filter = ("tipo", "armonizzata")
    search_fields = ("codice", "titolo")


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


for modello in (m.CondizioneOperativa, m.RiferimentoNormativo, m.Cliente, m.Fabbricante, m.LegislazioneUE):
    admin.site.register(modello)


NUMERO_NORME_PERICOLO = 10
CAMPI_NORME_PERICOLO = tuple(f"norma_{i}" for i in range(1, NUMERO_NORME_PERICOLO + 1))


class PericoloForm(forms.ModelForm):
    """Fino a 10 norme di riferimento per pericolo, una per selezione."""

    locals().update({nome: _campo_norma(i) for i, nome in enumerate(CAMPI_NORME_PERICOLO, start=1)})

    class Meta:
        model = m.Pericolo
        fields = ["codice", "descrizione"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        attuali = list(self.instance.norme.order_by("codice")) if self.instance.pk else []
        for campo, norma in zip(CAMPI_NORME_PERICOLO, attuali):
            self.initial[campo] = norma.pk

    def _save_m2m(self):
        super()._save_m2m()
        scelte = [self.cleaned_data.get(campo) for campo in CAMPI_NORME_PERICOLO]
        self.instance.norme.set(list(dict.fromkeys(n for n in scelte if n)))


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


@admin.register(m.Figura)
class FiguraAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "ordine")
    list_editable = ("ordine",)


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
