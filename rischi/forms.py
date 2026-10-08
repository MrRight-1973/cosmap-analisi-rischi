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
    Norma,
    RequisitoRESS,
    Revisione,
    RiferimentoNormativo,
    SchedaAnalisi,
    SchedaModello,
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
    """Moduli della macchina e, per ogni modulo, le sue schede modello da attivare."""

    moduli = SceltaModuli(
        help_text="Aggiungendo un modulo o una scheda, le schede entrano nella bozza come proposte. Togliendoli "
        "escono le schede ancora da decidere; quelle già decise restano e vanno scartate a mano.",
    )
    schede = forms.ModelMultipleChoiceField(
        SchedaModello.objects.filter(modulo__attivo=True), required=False, widget=forms.CheckboxSelectMultiple
    )
    # Presente solo quando la pagina mostra le schede: senza, le schede escluse restano come sono.
    con_schede = forms.BooleanField(required=False, widget=forms.HiddenInput, initial=True)

    def escluse(self):
        """Schede modello non spuntate, o None se la pagina non le mostrava."""
        if not self.cleaned_data.get("con_schede"):
            return None
        return SchedaModello.objects.filter(modulo__attivo=True).exclude(
            pk__in=[s.pk for s in self.cleaned_data["schede"]]
        )

    def gruppi(self):
        """[(modulo, spuntato, [(scheda, spuntata)])] per disegnare moduli e schede annidati."""
        if self.is_bound:
            moduli = {str(v) for v in self.data.getlist("moduli")}
            schede = {str(v) for v in self.data.getlist("schede")}
        else:
            moduli = {str(x.pk) for x in self.initial.get("moduli", [])}
            schede = {str(x.pk) for x in self.initial.get("schede", [])}
        elenco = SchedaModello.objects.filter(modulo__attivo=True).select_related("requisito")
        per_modulo = {}
        for scheda in elenco:
            per_modulo.setdefault(scheda.modulo_id, []).append((scheda, str(scheda.pk) in schede))
        return [
            (modulo, str(modulo.pk) in moduli, sorted(per_modulo.get(modulo.pk, []), key=lambda v: v[0].codice))
            for modulo in self.fields["moduli"].queryset
        ]


CAMPI_CONSIDERAZIONI = (
    "considerazioni_limiti",
    "considerazioni_pericoli",
    "considerazioni_soggetti",
    "considerazioni_stima_iniziale",
    "considerazioni_riduzione",
    "considerazioni_stima_finale",
)

# Norme richiamate nella sezione 1 della scheda: venti selezioni sotto le note (a video compaiono
# quelle compilate più una vuota, vedi rischi/static/rischi/scheda.js).
NUMERO_NORME = 20
CAMPI_NORME = tuple(f"norma_{i}" for i in range(1, NUMERO_NORME + 1))


def _campo_norma(numero):
    campo = forms.ModelChoiceField(
        Norma.objects.order_by("codice"), required=False, label=f"Norma {numero}", empty_label="–"
    )
    campo.label_from_instance = lambda n: f"{n.codice} – {n.titolo[:90]}" if n.titolo else n.codice
    return campo


def campi_norme():
    """{"norma_1": campo, …}: da aggiungere al corpo della classe del form con locals().update(...)."""
    return {nome: _campo_norma(i) for i, nome in enumerate(CAMPI_NORME, start=1)}


class NormeSchedaMixin:
    """Le selezioni norma_1…norma_20 leggono e scrivono il campo molti-a-molti `norme` della scheda."""

    def campi_norma(self):
        return [self[campo] for campo in CAMPI_NORME]

    def _prepara_norme(self):
        attuali = list(self.instance.norme.order_by("codice")) if self.instance.pk else []
        for campo, norma in zip(CAMPI_NORME, attuali):
            self.initial[campo] = norma.pk

    def norme_scelte(self):
        scelte = [self.cleaned_data.get(campo) for campo in CAMPI_NORME]
        return list(dict.fromkeys(n for n in scelte if n))

    def _save_m2m(self):
        super()._save_m2m()
        self.instance.norme.set(self.norme_scelte())


class SchedaForm(NormeSchedaMixin, forms.ModelForm):
    se_iniziale = _scelta(VALORI_SE)
    fr_iniziale = _scelta(VALORI_FR)
    pr_iniziale = _scelta(VALORI_PR)
    av_iniziale = _scelta(VALORI_AV)
    se_finale = _scelta(VALORI_SE)
    fr_finale = _scelta(VALORI_FR)
    pr_finale = _scelta(VALORI_PR)
    av_finale = _scelta(VALORI_AV)
    locals().update(campi_norme())  # norma_1 … norma_20

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
        "note",
        *CAMPI_NORME,
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
            "soggetti": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, riferimento=None, metodo=None, **kwargs):
        super().__init__(*args, **kwargs)
        if riferimento:
            self.fields["requisito"].queryset = RequisitoRESS.objects.filter(riferimento=riferimento)
        self.fields["soggetti"].help_text = (
            "Chi è esposto al pericolo: operatori e persone esposte. "
            "Le figure si aggiungono nella libreria (Figure, soggetti esposti)."
        )
        descrivi_fattori(self.fields, metodo)
        self._prepara_norme()

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


ApplicabilitaFormSet = modelformset_factory(
    ApplicabilitaRequisito,
    fields=["applicabile", "motivazione"],
    extra=0,
    widgets={"motivazione": forms.Textarea(attrs={"rows": 1})},
)


class NotaForm(forms.Form):
    testo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
