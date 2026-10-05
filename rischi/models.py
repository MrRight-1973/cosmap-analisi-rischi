"""Modello dati dell'analisi dei rischi.

Due mondi separati:
- libreria: moduli, schede modello, requisiti, pericoli, norme, metodo di stima;
- analisi di commessa: commessa -> macchina -> analisi -> revisione -> schede.

Ogni revisione contiene una copia completa delle schede: modificare la
libreria non altera mai un'analisi esistente.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


# ---------------------------------------------------------------------------
# Metodo di stima (ISO/TR 14121-2, metodo ibrido)
# ---------------------------------------------------------------------------


class Esito(models.TextChoices):
    OK = "OK", "OK"
    SUGGERITE = "SUGGERITE", "Misure suggerite"
    RICHIESTE = "RICHIESTE", "Misure richieste"


class MetodoStima(models.Model):
    versione = models.CharField(max_length=40, unique=True)
    descrizione = models.TextField(blank=True)
    attivo = models.BooleanField(
        default=False, help_text="Metodo usato per le nuove revisioni."
    )

    class Meta:
        verbose_name = "metodo di stima"
        verbose_name_plural = "metodi di stima"

    def __str__(self):
        return self.versione

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.attivo:
            MetodoStima.objects.exclude(pk=self.pk).update(attivo=False)

    @classmethod
    def corrente(cls):
        return cls.objects.filter(attivo=True).first()

    def esito(self, se, cl):
        """Esito della matrice per gravità Se e classe Cl, o None se fuori matrice."""
        if se is None or cl is None:
            return None
        cella = (
            self.celle.filter(se=se, fascia__cl_min__lte=cl, fascia__cl_max__gte=cl)
            .select_related("fascia")
            .first()
        )
        return cella.esito if cella else None


class ScalaFattore(models.Model):
    class Fattore(models.TextChoices):
        SE = "Se", "Se – Gravità"
        FR = "Fr", "Fr – Frequenza di esposizione"
        PR = "Pr", "Pr – Probabilità dell'evento"
        AV = "Av", "Av – Possibilità di evitare il danno"

    metodo = models.ForeignKey(MetodoStima, on_delete=models.CASCADE, related_name="scale")
    fattore = models.CharField(max_length=2, choices=Fattore.choices)
    valore = models.PositiveSmallIntegerField()
    descrizione = models.CharField(max_length=200)

    class Meta:
        verbose_name = "valore di scala"
        verbose_name_plural = "scale dei fattori"
        ordering = ["metodo", "fattore", "-valore"]

    def __str__(self):
        return f"{self.fattore} {self.valore}: {self.descrizione}"


class FasciaClasse(models.Model):
    metodo = models.ForeignKey(MetodoStima, on_delete=models.CASCADE, related_name="fasce")
    cl_min = models.PositiveSmallIntegerField()
    cl_max = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "fascia di classe"
        verbose_name_plural = "fasce di classe"
        ordering = ["metodo", "cl_min"]

    def __str__(self):
        return f"Cl {self.cl_min}-{self.cl_max}"


class CellaMatrice(models.Model):
    metodo = models.ForeignKey(MetodoStima, on_delete=models.CASCADE, related_name="celle")
    se = models.PositiveSmallIntegerField()
    fascia = models.ForeignKey(FasciaClasse, on_delete=models.CASCADE)
    esito = models.CharField(max_length=10, choices=Esito.choices)

    class Meta:
        verbose_name = "cella della matrice"
        verbose_name_plural = "matrice"
        unique_together = [("metodo", "se", "fascia")]
        ordering = ["metodo", "-se", "fascia__cl_min"]

    def __str__(self):
        return f"Se {self.se} / {self.fascia}: {self.get_esito_display()}"


# ---------------------------------------------------------------------------
# Libreria
# ---------------------------------------------------------------------------


class RiferimentoNormativo(models.Model):
    """Profilo normativo (per ora solo il Regolamento UE 2023/1230)."""

    codice = models.CharField(max_length=40, unique=True)
    nome = models.CharField(max_length=200)

    class Meta:
        verbose_name = "riferimento normativo"
        verbose_name_plural = "riferimenti normativi"

    def __str__(self):
        return self.codice


class RequisitoRESS(models.Model):
    riferimento = models.ForeignKey(RiferimentoNormativo, on_delete=models.PROTECT)
    codice = models.CharField(max_length=20, help_text="Punto dell'Allegato III del Regolamento.")
    titolo = models.CharField(max_length=200)
    codice_direttiva = models.CharField(
        max_length=20, blank=True, help_text="Punto dell'Allegato I della Direttiva 2006/42/CE."
    )
    nuovo = models.BooleanField(default=False, help_text="Requisito introdotto dal Regolamento.")
    novita = models.TextField("novità del Regolamento", blank=True)
    azione = models.TextField("azione per la libreria", blank=True)
    ordine = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "requisito RESS"
        verbose_name_plural = "requisiti RESS"
        unique_together = [("riferimento", "codice")]
        ordering = ["riferimento", "ordine"]

    def __str__(self):
        return f"{self.codice} {self.titolo}"


class Pericolo(models.Model):
    codice = models.CharField(max_length=20, unique=True, help_text="EN ISO 12100, allegato B.")
    descrizione = models.CharField(max_length=300)

    class Meta:
        verbose_name_plural = "pericoli"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} {self.descrizione}"


class Norma(models.Model):
    class Tipo(models.TextChoices):
        A = "A", "Tipo A"
        B = "B", "Tipo B"
        C = "C", "Tipo C"
        ALTRO = "-", "Altro"

    codice = models.CharField(max_length=60, unique=True)
    titolo = models.CharField(max_length=300, blank=True)
    tipo = models.CharField(max_length=1, choices=Tipo.choices, default=Tipo.ALTRO)
    edizione_citata = models.CharField(max_length=40, blank=True)
    edizione_vigente = models.CharField(max_length=40, blank=True)
    armonizzata = models.BooleanField(
        default=False, help_text="Presente nell'elenco delle norme armonizzate per il Regolamento."
    )
    nota = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "norme"
        ordering = ["codice"]

    def __str__(self):
        return self.codice


class CondizioneOperativa(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "condizione operativa"
        verbose_name_plural = "condizioni operative"
        ordering = ["ordine"]

    def __str__(self):
        return self.nome


class Caratteristica(models.Model):
    """Caratteristica della macchina che attiva uno o più moduli."""

    nome = models.CharField(max_length=150, unique=True)
    descrizione = models.TextField(blank=True)

    class Meta:
        verbose_name = "caratteristica macchina"
        verbose_name_plural = "caratteristiche macchina"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Modulo(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    descrizione = models.TextField(blank=True)
    sempre_attivo = models.BooleanField(default=False)
    caratteristiche = models.ManyToManyField(
        Caratteristica,
        blank=True,
        related_name="moduli",
        help_text="Il modulo si attiva se la macchina ha almeno una di queste caratteristiche.",
    )
    attivo = models.BooleanField(default=True)
    ordine = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name_plural = "moduli"
        ordering = ["ordine", "nome"]

    def __str__(self):
        return self.nome


class TipoMisura(models.TextChoices):
    PROGETTAZIONE = "PROG", "Progettazione intrinsecamente sicura"
    PROTEZIONE = "PROT", "Protezione e misure complementari"
    INFORMAZIONE = "INFO", "Informazioni per l'uso"
    DA_CLASSIFICARE = "DACL", "Da classificare"


class Stima(models.Model):
    """Campi comuni a scheda modello e scheda dell'analisi."""

    zona_impianto = models.CharField(max_length=60, blank=True)
    zona_pericolosa = models.TextField(blank=True)
    se_iniziale = models.PositiveSmallIntegerField("Se iniziale", null=True, blank=True)
    fr_iniziale = models.PositiveSmallIntegerField("Fr iniziale", null=True, blank=True)
    pr_iniziale = models.PositiveSmallIntegerField("Pr iniziale", null=True, blank=True)
    av_iniziale = models.PositiveSmallIntegerField("Av iniziale", null=True, blank=True)
    se_finale = models.PositiveSmallIntegerField("Se finale", null=True, blank=True)
    fr_finale = models.PositiveSmallIntegerField("Fr finale", null=True, blank=True)
    pr_finale = models.PositiveSmallIntegerField("Pr finale", null=True, blank=True)
    av_finale = models.PositiveSmallIntegerField("Av finale", null=True, blank=True)
    testo_istruzioni = models.TextField("indicazioni per le istruzioni / rischio residuo", blank=True)
    note = models.TextField(blank=True)

    class Meta:
        abstract = True

    @staticmethod
    def _cl(fr, pr, av):
        if None in (fr, pr, av):
            return None
        return fr + pr + av

    @property
    def cl_iniziale(self):
        return self._cl(self.fr_iniziale, self.pr_iniziale, self.av_iniziale)

    @property
    def cl_finale(self):
        return self._cl(self.fr_finale, self.pr_finale, self.av_finale)

    @property
    def ha_stima_iniziale(self):
        return self.se_iniziale is not None and self.cl_iniziale is not None

    @property
    def ha_stima_finale(self):
        return self.se_finale is not None and self.cl_finale is not None


class SchedaModello(Stima):
    class Stato(models.TextChoices):
        BOZZA = "BOZZA", "Bozza"
        VALIDATA = "VALIDATA", "Validata"

    codice = models.CharField(max_length=20, unique=True)
    modulo = models.ForeignKey(Modulo, on_delete=models.PROTECT, related_name="schede")
    requisito = models.ForeignKey(RequisitoRESS, on_delete=models.PROTECT, related_name="schede_modello")
    condizioni = models.ManyToManyField(CondizioneOperativa, blank=True)
    pericoli = models.ManyToManyField(Pericolo, blank=True)
    norme = models.ManyToManyField(Norma, blank=True)
    scheda_originale = models.CharField(max_length=40, blank=True, help_text="Riferimento alla valutazione di origine.")
    stato = models.CharField(max_length=10, choices=Stato.choices, default=Stato.BOZZA)

    class Meta:
        verbose_name = "scheda modello"
        verbose_name_plural = "schede modello"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} – {self.requisito.codice} {self.requisito.titolo}"


class MisuraModello(models.Model):
    scheda = models.ForeignKey(SchedaModello, on_delete=models.CASCADE, related_name="misure")
    ordine = models.PositiveSmallIntegerField(default=0)
    tipo = models.CharField(max_length=4, choices=TipoMisura.choices, default=TipoMisura.DA_CLASSIFICARE)
    testo = models.TextField()
    norma = models.ForeignKey(Norma, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "misura"
        verbose_name_plural = "misure di protezione"
        ordering = ["ordine", "pk"]

    def __str__(self):
        return self.testo[:60]


# ---------------------------------------------------------------------------
# Commessa e analisi
# ---------------------------------------------------------------------------


class Fabbricante(models.Model):
    """Dati fissi per la dichiarazione UE (una sola riga)."""

    ragione_sociale = models.CharField(max_length=200)
    indirizzo = models.TextField()
    partita_iva = models.CharField("partita IVA", max_length=20, blank=True)
    luogo = models.CharField("luogo di emissione delle dichiarazioni", max_length=100, blank=True)
    persona_fascicolo = models.CharField(
        "persona autorizzata a costituire il fascicolo tecnico", max_length=200, blank=True
    )
    indirizzo_persona_fascicolo = models.TextField(blank=True)
    firmatario = models.CharField(max_length=200, blank=True)
    qualifica_firmatario = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "dati del fabbricante"
        verbose_name_plural = "dati del fabbricante"

    def __str__(self):
        return self.ragione_sociale

    @classmethod
    def corrente(cls):
        return cls.objects.first()


class LegislazioneUE(models.Model):
    """Altra normativa di armonizzazione da citare nella dichiarazione (es. EMC, RoHS)."""

    codice = models.CharField(max_length=40, unique=True, help_text="Es. 2014/30/UE")
    titolo = models.CharField(max_length=300)
    titolo_en = models.CharField("titolo in inglese", max_length=300, blank=True)
    predefinita = models.BooleanField(default=False, help_text="Proposta per le nuove macchine.")

    class Meta:
        verbose_name = "legislazione UE"
        verbose_name_plural = "legislazioni UE"
        ordering = ["codice"]

    def __str__(self):
        return f"{self.codice} {self.titolo}"


class Cliente(models.Model):
    ragione_sociale = models.CharField(max_length=200)
    indirizzo = models.TextField(blank=True)
    paese = models.CharField(max_length=60, blank=True)

    class Meta:
        verbose_name_plural = "clienti"
        ordering = ["ragione_sociale"]

    def __str__(self):
        return self.ragione_sociale


class Commessa(models.Model):
    numero = models.CharField(max_length=30, unique=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="commesse")
    descrizione = models.CharField(max_length=300, blank=True)
    anno = models.PositiveSmallIntegerField()
    paese_destinazione = models.CharField(max_length=60, blank=True)
    riferimento = models.ForeignKey(RiferimentoNormativo, on_delete=models.PROTECT)

    class Meta:
        verbose_name_plural = "commesse"
        ordering = ["-anno", "-numero"]

    def __str__(self):
        return f"{self.numero} – {self.cliente}"


class Macchina(models.Model):
    class Tipo(models.TextChoices):
        MACCHINA = "MACCHINA", "Macchina"
        INSIEME = "INSIEME", "Insieme di macchine"
        QUASI = "QUASI", "Quasi-macchina"

    commessa = models.ForeignKey(Commessa, on_delete=models.PROTECT, related_name="macchine")
    denominazione = models.CharField(max_length=200)
    modello = models.CharField(max_length=100, blank=True)
    matricola = models.CharField(max_length=60, blank=True)
    anno_costruzione = models.PositiveSmallIntegerField(null=True, blank=True)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.MACCHINA)
    materiali = models.TextField("materiali lavorati", blank=True)
    funzione = models.TextField(
        blank=True, help_text="Denominazione generica e funzione, come compare nella dichiarazione."
    )
    caratteristiche = models.ManyToManyField(Caratteristica, blank=True, related_name="macchine")
    altre_legislazioni = models.ManyToManyField(
        LegislazioneUE, blank=True, help_text="Oltre al Regolamento (UE) 2023/1230."
    )
    organismo_notificato = models.TextField(
        blank=True,
        help_text="Solo per le macchine dell'Allegato I del Regolamento: nome, numero, procedura e certificato.",
    )

    class Meta:
        verbose_name_plural = "macchine"

    def __str__(self):
        base = self.modello or self.denominazione
        return f"{base} matr. {self.matricola}" if self.matricola else base


class Analisi(models.Model):
    class Origine(models.TextChoices):
        LIBRERIA = "LIBRERIA", "Dai moduli della libreria"
        COPIA = "COPIA", "Copia di un'altra analisi"

    macchina = models.OneToOneField(Macchina, on_delete=models.PROTECT, related_name="analisi")
    origine = models.CharField(max_length=10, choices=Origine.choices)
    copiata_da = models.ForeignKey(
        "Revisione", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    creata_il = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "analisi"

    def __str__(self):
        return f"Analisi {self.macchina.commessa.numero} – {self.macchina}"

    @property
    def revisione_corrente(self):
        return self.revisioni.order_by("-numero").first()

    @property
    def revisione_approvata(self):
        return self.revisioni.filter(stato=Revisione.Stato.APPROVATA).order_by("-numero").first()


class RevisioneBloccata(ValidationError):
    pass


class Revisione(models.Model):
    class Stato(models.TextChoices):
        BOZZA = "BOZZA", "Bozza"
        IN_VERIFICA = "IN_VERIFICA", "In verifica"
        APPROVATA = "APPROVATA", "Approvata"
        SOSTITUITA = "SOSTITUITA", "Sostituita"

    analisi = models.ForeignKey(Analisi, on_delete=models.PROTECT, related_name="revisioni")
    numero = models.PositiveSmallIntegerField()
    motivo = models.TextField(blank=True)
    stato = models.CharField(max_length=12, choices=Stato.choices, default=Stato.BOZZA)
    metodo = models.ForeignKey(MetodoStima, on_delete=models.PROTECT)
    creata_il = models.DateTimeField(auto_now_add=True)
    compilata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    inviata_il = models.DateTimeField(null=True, blank=True)
    verificata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    verificata_il = models.DateTimeField(null=True, blank=True)
    approvata_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    approvata_il = models.DateTimeField(null=True, blank=True)
    nota_verifica = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "revisioni"
        unique_together = [("analisi", "numero")]
        ordering = ["analisi", "-numero"]

    def __str__(self):
        return f"{self.analisi} rev. {self.numero}"

    @property
    def modificabile(self):
        return self.stato == self.Stato.BOZZA

    def verifica_modificabile(self):
        if not self.modificabile:
            raise RevisioneBloccata(
                f"La revisione {self.numero} è {self.get_stato_display().lower()}: non è modificabile."
            )


class ContenutoRevisione(models.Model):
    """Base per i dati che appartengono a una revisione e si bloccano con essa."""

    class Meta:
        abstract = True

    def _revisione(self):
        return self.revisione

    def save(self, *args, **kwargs):
        self._revisione().verifica_modificabile()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._revisione().verifica_modificabile()
        return super().delete(*args, **kwargs)


class SchedaAnalisi(ContenutoRevisione, Stima):
    class Decisione(models.TextChoices):
        PROPOSTA = "PROPOSTA", "Da decidere"
        CONFERMATA = "CONFERMATA", "Confermata"
        MODIFICATA = "MODIFICATA", "Modificata"
        SCARTATA = "SCARTATA", "Scartata"
        AGGIUNTA = "AGGIUNTA", "Aggiunta a mano"

    revisione = models.ForeignKey(Revisione, on_delete=models.CASCADE, related_name="schede")
    origine = models.ForeignKey(
        SchedaModello, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    codice = models.CharField(max_length=20, blank=True)
    modulo = models.ForeignKey(Modulo, on_delete=models.PROTECT)
    requisito = models.ForeignKey(RequisitoRESS, on_delete=models.PROTECT)
    condizioni = models.ManyToManyField(CondizioneOperativa, blank=True)
    pericoli = models.ManyToManyField(Pericolo, blank=True)
    norme = models.ManyToManyField(Norma, blank=True)
    decisione = models.CharField(max_length=10, choices=Decisione.choices, default=Decisione.PROPOSTA)
    motivazione = models.TextField(blank=True)
    decisa_da = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    decisa_il = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "scheda dell'analisi"
        verbose_name_plural = "schede dell'analisi"
        ordering = ["modulo__ordine", "requisito__ordine", "codice"]

    def __str__(self):
        return f"{self.codice or 'nuova'} – {self.requisito.codice} {self.requisito.titolo}"

    def clean(self):
        if self.decisione == self.Decisione.SCARTATA and not self.motivazione.strip():
            raise ValidationError({"motivazione": "Per scartare una scheda serve la motivazione."})

    @property
    def esito_iniziale(self):
        return self.revisione.metodo.esito(self.se_iniziale, self.cl_iniziale)

    @property
    def esito_finale(self):
        return self.revisione.metodo.esito(self.se_finale, self.cl_finale)

    @property
    def attiva(self):
        return self.decisione != self.Decisione.SCARTATA


class MisuraAnalisi(ContenutoRevisione):
    scheda = models.ForeignKey(SchedaAnalisi, on_delete=models.CASCADE, related_name="misure")
    ordine = models.PositiveSmallIntegerField(default=0)
    tipo = models.CharField(max_length=4, choices=TipoMisura.choices, default=TipoMisura.DA_CLASSIFICARE)
    testo = models.TextField()
    norma = models.ForeignKey(Norma, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "misura"
        verbose_name_plural = "misure di protezione"
        ordering = ["ordine", "pk"]

    def _revisione(self):
        return self.scheda.revisione

    def __str__(self):
        return self.testo[:60]


class ApplicabilitaRequisito(ContenutoRevisione):
    revisione = models.ForeignKey(Revisione, on_delete=models.CASCADE, related_name="applicabilita")
    requisito = models.ForeignKey(RequisitoRESS, on_delete=models.PROTECT)
    applicabile = models.BooleanField(default=True)
    motivazione = models.TextField(blank=True)

    class Meta:
        verbose_name = "applicabilità requisito"
        verbose_name_plural = "applicabilità requisiti"
        unique_together = [("revisione", "requisito")]
        ordering = ["requisito__ordine"]

    def __str__(self):
        return f"{self.requisito.codice}: {'applicabile' if self.applicabile else 'non applicabile'}"


class DocumentoGenerato(models.Model):
    class Tipo(models.TextChoices):
        VALUTAZIONE = "VALUTAZIONE", "Valutazione dei rischi"
        RESIDUI = "RESIDUI", "Elenco dei rischi residui"
        DICHIARAZIONE = "DICHIARAZIONE", "Dichiarazione UE di conformità"

    revisione = models.ForeignKey(Revisione, on_delete=models.PROTECT, related_name="documenti")
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    lingua = models.CharField(max_length=2, default="it")
    definitivo = models.BooleanField(default=False, help_text="Generato da una revisione approvata.")
    file = models.FileField(upload_to="documenti/%Y/")
    generato_il = models.DateTimeField(auto_now_add=True)
    generato_da = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name = "documento generato"
        verbose_name_plural = "documenti generati"
        ordering = ["-generato_il"]


# ---------------------------------------------------------------------------
# Registro modifiche
# ---------------------------------------------------------------------------


class RegistroModifica(models.Model):
    class Azione(models.TextChoices):
        CREA = "CREA", "Creazione"
        MODIFICA = "MODIFICA", "Modifica"
        ELIMINA = "ELIMINA", "Eliminazione"

    quando = models.DateTimeField(auto_now_add=True)
    utente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    azione = models.CharField(max_length=10, choices=Azione.choices)
    tabella = models.CharField(max_length=60)
    oggetto_id = models.CharField(max_length=40)
    descrizione = models.CharField(max_length=300)
    modifiche = models.JSONField(default=dict, help_text="Campo: [prima, dopo].")

    class Meta:
        verbose_name = "modifica registrata"
        verbose_name_plural = "registro modifiche"
        ordering = ["-quando"]

    def __str__(self):
        return f"{self.quando:%d/%m/%Y %H:%M} {self.utente} {self.get_azione_display()} {self.tabella}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Il registro modifiche non si può modificare.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Il registro modifiche non si può cancellare.")
