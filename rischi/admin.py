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


class SceltaScheda(forms.ModelMultipleChoiceField):
    def label_from_instance(self, scheda):
        return f"{scheda.codice} – {scheda.requisito.codice} {scheda.requisito.titolo} ({scheda.modulo.nome})"


class ModuloForm(forms.ModelForm):
    schede = SceltaScheda(
        m.SchedaModello.objects.select_related("modulo", "requisito"),
        required=False,
        widget=FilteredSelectMultiple("schede", is_stacked=False),
        label="Schede del modulo",
        help_text="Ogni scheda appartiene a un solo modulo: sceglierne una di un altro modulo la sposta qui. "
        "Tra parentesi il modulo attuale.",
    )

    class Meta:
        model = m.Modulo
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["schede"].initial = self.instance.schede.all()

    def clean(self):
        dati = super().clean()
        if self.instance.pk and "schede" in dati:
            tolte = self.instance.schede.exclude(pk__in=[s.pk for s in dati["schede"]])
            if tolte.exists():
                self.add_error(
                    "schede",
                    "Una scheda non può restare senza modulo: per togliere "
                    + ", ".join(s.codice for s in tolte)
                    + " sceglila dalla pagina dell'altro modulo.",
                )
        return dati

    def _assegna_schede(self, modulo):
        for scheda in self.cleaned_data["schede"]:
            if scheda.modulo_id != modulo.pk:
                scheda.modulo = modulo
                scheda.save()

    def save(self, commit=True):
        modulo = super().save(commit=commit)
        if commit:
            self._assegna_schede(modulo)
        else:
            vecchio_save_m2m = self.save_m2m

            def save_m2m():
                vecchio_save_m2m()
                self._assegna_schede(modulo)

            self.save_m2m = save_m2m
        return modulo


@admin.register(m.Modulo)
class ModuloAdmin(admin.ModelAdmin):
    form = ModuloForm
    list_display = ("nome", "condizione", "sempre_attivo", "numero_schede", "attivo", "ordine")
    list_editable = ("ordine",)

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


@admin.register(m.Commessa)
class CommessaAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "anno", "riferimento")
    search_fields = ("numero", "cliente__ragione_sociale")


@admin.register(m.Macchina)
class MacchinaAdmin(admin.ModelAdmin):
    list_display = ("commessa", "denominazione", "modello", "matricola", "tipo")

