from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import FilteredSelectMultiple

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
    list_display = ("nome", "sempre_attivo", "attivato_da", "attivo", "ordine")
    list_editable = ("ordine",)
    exclude = ("caratteristiche",)
    readonly_fields = ("attivato_da",)

    @admin.display(description="attivato da")
    def attivato_da(self, obj):
        if obj.sempre_attivo:
            return "sempre"
        return ", ".join(c.nome for c in obj.caratteristiche.all()) or "nessuna caratteristica"


class CaratteristicaForm(forms.ModelForm):
    moduli = forms.ModelMultipleChoiceField(
        m.Modulo.objects.filter(sempre_attivo=False),
        required=False,
        widget=FilteredSelectMultiple("moduli", is_stacked=False),
        label="Moduli da attivare",
        help_text="Quando la macchina ha questa caratteristica, l'analisi propone le schede di questi moduli.",
    )

    class Meta:
        model = m.Caratteristica
        fields = ["nome", "descrizione"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["moduli"].initial = self.instance.moduli.all()

    def save(self, commit=True):
        caratteristica = super().save(commit=commit)
        if commit:
            caratteristica.moduli.set(self.cleaned_data["moduli"])
        else:
            vecchio_save_m2m = self.save_m2m

            def save_m2m():
                vecchio_save_m2m()
                caratteristica.moduli.set(self.cleaned_data["moduli"])

            self.save_m2m = save_m2m
        return caratteristica


@admin.register(m.Caratteristica)
class CaratteristicaAdmin(admin.ModelAdmin):
    form = CaratteristicaForm
    list_display = ("nome", "moduli_attivati")
    search_fields = ("nome",)

    @admin.display(description="moduli attivati")
    def moduli_attivati(self, obj):
        return ", ".join(mo.nome for mo in obj.moduli.all())



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


@admin.register(m.Commessa)
class CommessaAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "anno", "riferimento")
    search_fields = ("numero", "cliente__ragione_sociale")


@admin.register(m.Macchina)
class MacchinaAdmin(admin.ModelAdmin):
    list_display = ("commessa", "denominazione", "modello", "matricola", "tipo")

