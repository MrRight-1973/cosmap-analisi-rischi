from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from . import models as m


class MisuraModelloInline(admin.StackedInline):
    model = m.MisuraModello
    extra = 0


class SchedaModelloForm(forms.ModelForm):
    class Meta:
        model = m.SchedaModello
        exclude = ("codice",)

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


@admin.register(m.Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ("nome", "sigla", "condizione", "sempre_attivo", "numero_schede", "attivo", "ordine")
    list_editable = ("ordine",)
    readonly_fields = ("elenco_schede",)

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

