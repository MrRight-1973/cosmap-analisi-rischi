from django import forms
from django.forms import inlineformset_factory, modelformset_factory

from .models import (
    ApplicabilitaRequisito,
    LegislazioneUE,
    Cliente,
    Commessa,
    Figura,
    FiguraMacchina,
    Macchina,
    MisuraAnalisi,
    Modulo,
    RequisitoRESS,
    Revisione,
    RiferimentoNormativo,
    SchedaAnalisi,
)

VALORI_SE = [(None, "–"), (1, "1"), (2, "2"), (3, "3"), (4, "4")]
VALORI_FR = [(None, "–"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]
VALORI_PR = [(None, "–"), (1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]
VALORI_AV = [(None, "–"), (1, "1"), (3, "3"), (5, "5")]


ETICHETTE_FATTORI = {
    "se": "Se – Gravità",
    "fr": "Fr – Frequenza di esposizione",
    "pr": "Pr – Probabilità dell'evento",
    "av": "Av – Possibilità di evitare il danno",
}


class SceltaModuli(forms.ModelMultipleChoiceField):
    def __init__(self, **kwargs):
        kwargs.setdefault("widget", forms.CheckboxSelectMultiple)
        kwargs.setdefault("required", False)
        kwargs.setdefault("label", "Moduli della libreria")
        super().__init__(Modulo.objects.filter(attivo=True), **kwargs)

    def label_from_instance(self, modulo):
        return f"{modulo.nome} ({modulo.condizione})" if modulo.condizione else modulo.nome


def _scelta(valori):
    return forms.TypedChoiceField(choices=valori, coerce=int, empty_value=None, required=False)


CAMPI_STIMA = {
    f"{fattore}_{quale}": valori
    for fattore, valori in (("se", VALORI_SE), ("fr", VALORI_FR), ("pr", VALORI_PR), ("av", VALORI_AV))
    for quale in ("iniziale", "finale")
}


def descrivi_fattori(campi, metodo):
    """Nome completo del fattore e, accanto a ogni valore, la descrizione delle scale del metodo."""
    descrizioni = metodo.descrizioni() if metodo else {}
    for nome, campo in campi.items():
        if nome not in CAMPI_STIMA:
            continue
        campo.label = ETICHETTE_FATTORI[nome[:2]]
        fattore = nome[:2].capitalize()
        campo.choices = [
            (v, f"{v} – {descrizioni[(fattore, v)]}" if (fattore, v) in descrizioni else e)
            for v, e in CAMPI_STIMA[nome]
        ]


class NuovaCommessaForm(forms.Form):
    ORIGINE = [("LIBRERIA", "Dai moduli della libreria"), ("COPIA", "Copiando un'analisi approvata")]

    numero = forms.CharField(label="Numero commessa", max_length=30)
    cliente = forms.ModelChoiceField(Cliente.objects.all(), required=False, label="Cliente esistente")
    nuovo_cliente = forms.CharField(label="…oppure nuovo cliente", max_length=200, required=False)
    paese_cliente = forms.CharField(label="Paese del cliente", max_length=60, required=False)
    anno = forms.IntegerField(min_value=2000, max_value=2100)
    descrizione = forms.CharField(max_length=300, required=False)
    paese_destinazione = forms.CharField(max_length=60, required=False, label="Paese di destinazione")
    riferimento = forms.ModelChoiceField(
        RiferimentoNormativo.objects.all(), label="Riferimento normativo", empty_label=None
    )

    denominazione = forms.CharField(label="Denominazione macchina", max_length=200)
    modello = forms.CharField(max_length=100, required=False)
    matricola = forms.CharField(max_length=60, required=False)
    anno_costruzione = forms.IntegerField(min_value=2000, max_value=2100, required=False)
    tipo = forms.ChoiceField(choices=Macchina.Tipo.choices, label="Tipo")
    materiali = forms.CharField(label="Materiali lavorati", widget=forms.Textarea(attrs={"rows": 2}), required=False)
    funzione = forms.CharField(
        label="Funzione",
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
        help_text="Come compare nella dichiarazione, es. \"lucidatura automatica di rubinetteria in ottone\".",
    )
    altre_legislazioni = forms.ModelMultipleChoiceField(
        LegislazioneUE.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Altra legislazione UE applicabile",
        initial=lambda: LegislazioneUE.objects.filter(predefinita=True),
    )
    moduli = SceltaModuli(
        initial=lambda: Modulo.objects.filter(attivo=True, sempre_attivo=True),
        help_text="Le schede di questi moduli vengono proposte nell'analisi. Si possono cambiare anche dopo, "
        "dai dati della macchina. Copiando un'analisi si prendono i moduli di quella.",
    )

    origine = forms.ChoiceField(choices=ORIGINE, widget=forms.RadioSelect, initial="LIBRERIA")
    copia_da = forms.ModelChoiceField(
        Revisione.objects.filter(stato=Revisione.Stato.APPROVATA).select_related(
            "analisi__macchina__commessa__cliente"
        ),
        required=False,
        label="Analisi da copiare",
    )

    def clean_numero(self):
        numero = self.cleaned_data["numero"].strip()
        if Commessa.objects.filter(numero=numero).exists():
            raise forms.ValidationError("Esiste già una commessa con questo numero.")
        return numero

    def clean(self):
        dati = super().clean()
        if not dati.get("cliente") and not (dati.get("nuovo_cliente") or "").strip():
            self.add_error("cliente", "Scegli un cliente o scrivi il nome di uno nuovo.")
        if dati.get("origine") == "COPIA" and not dati.get("copia_da"):
            self.add_error("copia_da", "Scegli l'analisi da copiare.")
        return dati


class MacchinaForm(forms.ModelForm):
    class Meta:
        model = Macchina
        fields = [
            "denominazione",
            "modello",
            "matricola",
            "anno_costruzione",
            "tipo",
            "funzione",
            "materiali",
            "altre_legislazioni",
            "organismo_notificato",
        ]
        widgets = {
            "funzione": forms.Textarea(attrs={"rows": 2}),
            "materiali": forms.Textarea(attrs={"rows": 2}),
            "organismo_notificato": forms.Textarea(attrs={"rows": 2}),
            "altre_legislazioni": forms.CheckboxSelectMultiple,
        }


class ModuliMacchinaForm(forms.Form):
    moduli = SceltaModuli(
        help_text="Aggiungendo un modulo le sue schede entrano nella bozza come proposte. Togliendolo escono "
        "le sue schede ancora da decidere; quelle già decise restano e vanno scartate a mano.",
    )


CAMPI_CONSIDERAZIONI = (
    "considerazioni_limiti",
    "considerazioni_pericoli",
    "considerazioni_soggetti",
    "considerazioni_stima_iniziale",
    "considerazioni_riduzione",
    "considerazioni_stima_finale",
)


class SchedaForm(forms.ModelForm):
    se_iniziale = _scelta(VALORI_SE)
    fr_iniziale = _scelta(VALORI_FR)
    pr_iniziale = _scelta(VALORI_PR)
    av_iniziale = _scelta(VALORI_AV)
    se_finale = _scelta(VALORI_SE)
    fr_finale = _scelta(VALORI_FR)
    pr_finale = _scelta(VALORI_PR)
    av_finale = _scelta(VALORI_AV)

    CAMPI_CONTENUTO = (
        "modulo",
        "requisito",
        "zona_impianto",
        "zona_pericolosa",
        "condizioni",
        "pericoli",
        "soggetti",
        "se_iniziale",
        "fr_iniziale",
        "pr_iniziale",
        "av_iniziale",
        "se_finale",
        "fr_finale",
        "pr_finale",
        "av_finale",
        "testo_istruzioni",
        "norme",
        "note",
        *CAMPI_CONSIDERAZIONI,
    )

    class Meta:
        model = SchedaAnalisi
        fields = [
            "modulo",
            "requisito",
            "zona_impianto",
            "zona_pericolosa",
            "condizioni",
            "pericoli",
            "soggetti",
            "se_iniziale",
            "fr_iniziale",
            "pr_iniziale",
            "av_iniziale",
            "se_finale",
            "fr_finale",
            "pr_finale",
            "av_finale",
            "testo_istruzioni",
            "norme",
            "note",
            *CAMPI_CONSIDERAZIONI,
            "decisione",
            "motivazione",
        ]
        widgets = {
            "zona_pericolosa": forms.Textarea(attrs={"rows": 2}),
            "testo_istruzioni": forms.Textarea(attrs={"rows": 5}),
            "note": forms.Textarea(attrs={"rows": 2}),
            **{campo: forms.Textarea(attrs={"rows": 2}) for campo in CAMPI_CONSIDERAZIONI},
            "motivazione": forms.Textarea(attrs={"rows": 2}),
            "condizioni": forms.CheckboxSelectMultiple,
            "pericoli": forms.SelectMultiple(attrs={"size": 8}),
            "norme": forms.SelectMultiple(attrs={"size": 8}),
            "soggetti": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, riferimento=None, metodo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if riferimento:
            self.fields["requisito"].queryset = RequisitoRESS.objects.filter(riferimento=riferimento)
        self.fields["soggetti"].help_text = (
            "Chi è esposto al pericolo: operatori (RESS 1.1.1 d) e persone esposte (RESS 1.1.1 c). "
            "Chi sono su questa macchina si scrive nei dati della macchina."
        )
        descrivi_fattori(self.fields, metodo)

    def contenuto_cambiato(self):
        return any(campo in self.changed_data for campo in self.CAMPI_CONTENUTO)


MisureFormSet = inlineformset_factory(
    SchedaAnalisi,
    MisuraAnalisi,
    fields=["ordine", "tipo", "testo", "norma"],
    extra=1,
    can_delete=True,
    widgets={"testo": forms.Textarea(attrs={"rows": 4}), "ordine": forms.NumberInput(attrs={"style": "width:4em"})},
)


FigureMacchinaFormSet = inlineformset_factory(
    Macchina,
    FiguraMacchina,
    fields=["figura", "descrizione"],
    extra=1,
    can_delete=True,
    widgets={"descrizione": forms.Textarea(attrs={"rows": 1})},
)


ApplicabilitaFormSet = modelformset_factory(
    ApplicabilitaRequisito,
    fields=["applicabile", "motivazione"],
    extra=0,
    widgets={"motivazione": forms.Textarea(attrs={"rows": 1})},
)


class NotaForm(forms.Form):
    testo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
