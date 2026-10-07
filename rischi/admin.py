from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from . import models as m
from .forms import VALORI_AV, VALORI_FR, VALORI_PR, VALORI_SE, _scelta, descrivi_fattori


class MisuraModelloInline(admin.StackedInline):
    model = m.MisuraModello
    extra = 0
    verbose_name_plural = "Misure di protezione (ripari RESS 1.1.1 f, dispositivi di protezione 1.1.1 g)"


class SchedaModelloForm(forms.ModelForm):
    se_iniziale = _scelta(VALORI_SE)
    fr_iniziale = _scelta(VALORI_FR)
    pr_iniziale = _scelta(VALORI_PR)
    av_iniziale = _scelta(VALORI_AV)
    se_finale = _scelta(VALORI_SE)
    fr_finale = _scelta(VALORI_FR)
    pr_finale = _scelta(VALORI_PR)
    av_finale = _scelta(VALORI_AV)

    class Meta:
        model = m.SchedaModello
        exclude = ("codice",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        descrivi_fattori(self.fields, m.MetodoStima.corrente())

    def clean(self):
        dati = super().clean()
        modulo = dati.get("modulo")
        if modulo and not modulo.sigla:
            self.add_error("modulo", f"Il modulo \"{modulo}\" non ha la sigla: impostala nella pagina del modulo.")
        return dati


@admin.register(m.SchedaModello)
class SchedaModelloAdmin(admin.ModelAdmin):
    form = SchedaModelloForm
    list_display = ("codice", "modulo", "requisito", "zona_impianto", "stato")
    list_filter = ("modulo", "zona_impianto", "stato")
    search_fields = ("codice", "requisito__codice", "requisito__titolo", "testo_istruzioni")
    filter_horizontal = ("condizioni", "pericoli", "norme", "soggetti")
    readonly_fields = ("codice",)
    inlines = [MisuraModelloInline]
    # Stesso ordine della scheda nell'analisi; le misure stanno tra stima iniziale e finale
    # (vedi admin/rischi/schedamodello/change_form.html).
    fieldsets = (
        ("Identificazione", {
            "fields": ("codice", "modulo", "requisito", "zona_impianto", "zona_pericolosa",
                       "condizioni", "pericoli", "soggetti"),
        }),
        ("Stima iniziale del rischio (RESS 1.1.1 e)", {
            "fields": (("se_iniziale", "fr_iniziale", "pr_iniziale", "av_iniziale"),),
        }),
        ("Stima finale del rischio (RESS 1.1.1 e)", {
            "fields": (("se_finale", "fr_finale", "pr_finale", "av_finale"),
                       "testo_istruzioni", "norme", "note"),
        }),
        ("Libreria", {
            "fields": ("stato", "scheda_originale"),
        }),
    )

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
class RequisitoAdmin(admin.ModelAdmin):
    list_display = ("codice", "titolo", "codice_direttiva", "nuovo", "riferimento")
    list_filter = ("riferimento", "nuovo")
    search_fields = ("codice", "titolo")


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


for modello in (m.Pericolo, m.CondizioneOperativa, m.RiferimentoNormativo, m.Cliente, m.Fabbricante, m.LegislazioneUE):
    admin.site.register(modello)


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

