from django.contrib import admin

from . import models as m


class MisuraModelloInline(admin.StackedInline):
    model = m.MisuraModello
    extra = 0


@admin.register(m.SchedaModello)
class SchedaModelloAdmin(admin.ModelAdmin):
    list_display = ("codice", "modulo", "requisito", "zona_impianto", "stato")
    list_filter = ("modulo", "zona_impianto", "stato")
    search_fields = ("codice", "requisito__codice", "requisito__titolo", "testo_istruzioni")
    filter_horizontal = ("condizioni", "pericoli", "norme")
    inlines = [MisuraModelloInline]


@admin.register(m.Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ("nome", "sempre_attivo", "attivo", "ordine")
    list_editable = ("ordine",)



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


for modello in (m.Pericolo, m.CondizioneOperativa, m.Caratteristica, m.RiferimentoNormativo, m.Cliente, m.Fabbricante, m.LegislazioneUE):
    admin.site.register(modello)


@admin.register(m.Commessa)
class CommessaAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "anno", "riferimento")
    search_fields = ("numero", "cliente__ragione_sociale")


@admin.register(m.Macchina)
class MacchinaAdmin(admin.ModelAdmin):
    list_display = ("commessa", "denominazione", "modello", "matricola", "tipo")

