"""Primo catalogo delle soluzioni di protezione e EN ISO 12100 sempre applicata.

Le norme si collegano solo se sono già in libreria; il catalogo si completa dall'amministrazione."""

from django.db import migrations

PROG, PROT, INFO = "PROG", "PROT", "INFO"

SOLUZIONI = [
    ("Riparo fisso", PROT,
     "Riparo fisso fissato con elementi che richiedono un attrezzo per la rimozione, a distanza di sicurezza "
     "dalla zona pericolosa.", ["EN ISO 14120", "EN ISO 13857"]),
    ("Riparo mobile interbloccato", PROT,
     "Riparo mobile con dispositivo di interblocco: all'apertura i movimenti pericolosi si arrestano e non "
     "possono ripartire finché il riparo è aperto.", ["EN ISO 14120", "EN ISO 14119", "EN ISO 13849-1"]),
    ("Riparo mobile interbloccato con bloccaggio", PROT,
     "Riparo mobile interbloccato con bloccaggio: resta chiuso finché i movimenti pericolosi non sono "
     "terminati.", ["EN ISO 14120", "EN ISO 14119", "EN ISO 13849-1"]),
    ("Barriera fotoelettrica", PROT,
     "Barriera fotoelettrica di sicurezza posizionata alla distanza minima calcolata: l'interruzione arresta "
     "i movimenti pericolosi.", ["EN IEC 61496-1", "EN ISO 13855", "EN ISO 13849-1"]),
    ("Arresto di emergenza", PROT,
     "Dispositivi di arresto di emergenza a fungo rosso su fondo giallo, raggiungibili dalle postazioni di "
     "lavoro.", ["EN ISO 13850", "EN 60204-1"]),
    ("Prevenzione dell'avviamento inatteso", PROT,
     "Sezionatore lucchettabile e procedura di consegna per isolare e dissipare le energie prima "
     "dell'intervento.", ["EN ISO 14118", "EN 60204-1"]),
    ("Funzioni di sicurezza del sistema di comando", PROT,
     "Funzioni di sicurezza realizzate con il livello di prestazione richiesto (PLr).",
     ["EN ISO 13849-1", "EN ISO 13849-2"]),
    ("Aspirazione di polveri e sostanze", PROT,
     "Aspirazione localizzata alla fonte delle polveri e delle sostanze generate dalla lavorazione.",
     ["EN ISO 14123-1"]),
    ("Protezione dalle superfici calde", PROT,
     "Superfici calde segregate o isolate in modo da non superare i limiti di ustione al contatto.",
     ["EN ISO 13732-1"]),
    ("Spazi minimi contro lo schiacciamento", PROG,
     "Distanze tra parti mobili e fisse non inferiori agli spazi minimi per le parti del corpo esposte.",
     ["EN ISO 13854"]),
    ("Equipaggiamento elettrico conforme", PROG,
     "Equipaggiamento elettrico progettato e realizzato secondo la norma di riferimento.", ["EN 60204-1"]),
    ("Impianto pneumatico conforme", PROG,
     "Impianto pneumatico con valvola di sezionamento e scarico, componenti dimensionati per la pressione di "
     "esercizio.", ["EN ISO 4414"]),
    ("Riduzione del rumore alla fonte", PROG,
     "Scelte progettuali per ridurre l'emissione sonora alla fonte.", ["EN ISO 11688-1"]),
    ("Illuminazione integrata", PROG,
     "Illuminazione integrata nelle zone di lavoro, regolazione e manutenzione.", ["EN 1837"]),
    ("Postazione ergonomica", PROG,
     "Postazione di lavoro dimensionata secondo i principi ergonomici e i requisiti antropometrici.",
     ["EN 614-1", "EN ISO 14738"]),
    ("Piattaforme e passerelle", PROT,
     "Mezzi di accesso permanenti con piattaforme, passerelle e parapetti.", ["EN ISO 14122-2", "EN ISO 14122-3"]),
    ("Segnaletica di sicurezza", INFO,
     "Segnali di pericolo, divieto e obbligo applicati sulla macchina in prossimità del pericolo.",
     ["EN ISO 7010", "EN 61310-1"]),
    ("Istruzioni nel manuale", INFO,
     "Informazioni e avvertenze sul rischio residuo nel manuale di istruzioni.", ["EN ISO 20607"]),
]


def carica(apps, schema_editor):
    Norma = apps.get_model("rischi", "Norma")
    Soluzione = apps.get_model("rischi", "SoluzioneProtezione")
    Norma.objects.filter(codice="EN ISO 12100").update(sempre_applicata=True)
    for nome, tipo, testo, codici in SOLUZIONI:
        soluzione, creata = Soluzione.objects.get_or_create(nome=nome, defaults={"tipo": tipo, "testo": testo})
        if creata:
            soluzione.norme.set(Norma.objects.filter(codice__in=codici))


class Migration(migrations.Migration):
    dependencies = [("rischi", "0024_soluzioni_protezione_norme_tipo_c")]
    operations = [migrations.RunPython(carica, migrations.RunPython.noop)]
