"""Elenco dei pericoli rigenerato dal registro interno EN ISO 12100 (prospetto B.1, tre livelli).

Tutte le voci precedenti (prima estrazione 2020 e libreria NL) sono sostituite. Le schede della
libreria e delle analisi, comprese quelle delle revisioni approvate, passano ai nuovi codici
secondo le tabelle di corrispondenza qui sotto; il significato del pericolo resta lo stesso.
Le voci senza corrispondenza vengono eliminate e il loro numero è stampato a video.
"""

from django.db import migrations

PERICOLI = [
    ("1.1.1", "Forma (elementi taglienti, spigoli vivi, pezzi aguzzi)"),
    ("1.1.2", "Posizione relativa (zone di convergenza o ridotti spazi tra parti mobili)"),
    ("1.1.3", "Massa e stabilità (energia potenziale dovuta alla gravità)"),
    ("1.1.4", "Massa e velocità (energia cinetica di elementi in movimento)"),
    ("1.1.5", "Accelerazione o decelerazione inadeguata"),
    ("1.1.6", "Resistenza meccanica insufficiente degli elementi (rotture, cedimenti)"),
    ("1.2.1", "Pericolo di schiacciamento"),
    ("1.2.2", "Pericolo di cesoiamento"),
    ("1.2.3", "Pericolo di taglio o di sezionamento"),
    ("1.2.4", "Pericolo di impigliamento"),
    ("1.2.5", "Pericolo di trascinamento o d'intrappolamento"),
    ("1.2.6", "Pericolo di urto"),
    ("1.2.7", "Pericolo di perforazione o di puntura"),
    ("1.2.8", "Pericolo di attrito o di abrasione"),
    ("1.2.9", "Pericolo di eiezione o iniezione di fluido ad alta pressione"),
    ("2.1.1", "Contatto elettrico diretto (con parti normalmente in tensione)"),
    ("2.1.2", "Contatto elettrico indiretto (con parti andate in tensione per un guasto)"),
    ("2.1.3", "Avvicinamento a parti sotto alta tensione (effetto arco elettrico)"),
    ("2.2.1", "Fenomeni elettrostatici (scosse da cariche statiche accumulate)"),
    ("2.2.2", "Irraggiamento termico o proiezioni da cortocircuiti"),
    ("3.1.1", "Ustioni e scottature da contatto con oggetti o fluidi caldi, fiamme o esplosioni"),
    ("3.1.2", "Lesioni da contatto con superfici o fluidi a temperatura estremamente bassa (congelamento)"),
    ("3.2.1", "Danni alla salute causati da un ambiente di lavoro eccessivamente caldo o freddo"),
    ("4.1.1", "Perdita dell'udito (ipoacusia da trauma acustico o esposizione prolungata)"),
    ("4.1.2", "Acufene (ronzio o fischio permanente nelle orecchie)"),
    ("4.2.1", "Disturbi dell'equilibrio o senso di vertigine"),
    ("4.2.2", "Interferenza con la comunicazione verbale e mascheramento dei segnali acustici"),
    ("5.1.1", "Sindrome da vibrazioni mano-braccio (disturbi vascolari, neurologici e ossei)"),
    ("5.1.2", "Sindrome da vibrazioni corpo intero (traumi alla colonna vertebrale, lombalgie)"),
    ("6.1.1", "Radiazioni ionizzanti (fonti di raggi X, raggi gamma o particelle)"),
    ("6.1.2", "Campi elettromagnetici (unità CEM a bassa o alta frequenza)"),
    ("6.2.1", "Radiazioni ottiche artificiali (ROA): infrarossi, luce visibile estrema, ultravioletti"),
    ("6.2.2", "Radiazioni laser (danni irreversibili a occhi e pelle)"),
    ("7.1.1", "Pericoli tossici o nocivi per inalazione, ingestione o contatto con elementi chimici"),
    ("7.1.2", "Pericoli biologici o microbiologici (esposizione a virus o batteri nei liquidi)"),
    ("7.2.1", "Pericoli di incendio o combustione di materiali lavorati o fluidi di processo"),
    ("7.2.2", "Pericoli di esplosione (miscele di gas o accumuli di polveri combustibili)"),
    ("8.1.1", "Posture incongrue, faticose o sforzi fisici eccessivi"),
    ("8.1.2", "Movimenti ripetitivi o inadeguata considerazione dell'anatomia della mano/braccio"),
    ("8.2.1", "Progettazione errata o insufficiente dell'illuminazione locale sulla macchina"),
    ("8.2.2", "Sovraccarico mentale, stress o affaticamento da cattiva progettazione dell'interfaccia (HMI)"),
    ("9.1.1", "Fulminazione da scariche atmosferiche esterne"),
    ("9.1.2", "Condizioni meteorologiche estreme (vento forte, neve, temperature proibitive)"),
    ("9.2.1", "Mancanza di stabilità del suolo o pendenze (rischio di ribaltamento)"),
    ("9.2.2", "Rischio di scivolamento, inciampo o caduta a causa della conformazione dei piani"),
    ("10.1.1", "Rischi generati dall'azione simultanea di più fattori (es. vibrazioni + freddo + postura)"),
]

# Libreria NL (codici a due cifre, es. 1.01)
DA_NL = {
    "1.01": ["1.2.1"], "1.02": ["1.2.2"], "1.03": ["1.2.3"], "1.04": ["1.2.5"], "1.05": ["1.2.4"],
    "1.06": ["1.2.6"], "1.07": ["1.2.8"], "1.08": ["1.2.7"], "1.09": ["1.1.4", "1.1.6"], "1.10": ["1.1.3"],
    "1.11": ["1.2.9"], "1.12": ["1.1.4"],
    "2.01": ["2.1.1"], "2.02": ["2.1.2"], "2.03": ["2.2.1"], "2.04": ["2.2.2", "7.2.1"],
    "3.01": ["3.1.1"], "3.02": ["7.2.1"],
    "4.01": ["4.1.1"], "4.02": ["4.2.2"],
    "7.01": ["7.1.1"], "7.02": ["7.1.1"], "7.03": ["7.2.2"], "7.04": ["7.1.1"],
    "8.01": ["8.1.1", "8.1.2"], "8.02": ["8.1.1"], "8.03": ["8.2.1"], "8.04": ["8.2.2"],
    "9.01": ["9.2.2"], "9.02": ["9.2.2"], "9.03": ["1.2.5"],
    "10.01": ["10.1.1"], "10.02": ["10.1.1"], "10.03": ["10.1.1"],
}

# Prima estrazione 2020 (schede LIB)
DA_LIB = {
    "1.1.1": ["1.2.1"], "1.1.2": ["1.2.2"], "1.1.3": ["1.2.3"], "1.1.4": ["1.2.4"], "1.1.5": ["1.2.5"],
    "1.1.6": ["1.2.6"], "1.1.7": ["1.2.7"], "1.1.8": ["1.2.8"], "1.1.9": ["1.2.9"],
    "1.2.1": ["1.1.1"], "1.2.2": ["1.1.2"], "1.2.3": ["1.1.3"], "1.2.4": ["1.1.4"],
    "10.8": ["9.2.2"], "11.3": ["1.1.3"],
    "2.1": ["2.1.1"], "2.2": ["2.1.2"], "2.4": ["2.1.1", "2.1.2"], "2.5": ["2.2.1"], "2.6": ["2.2.2"],
    "2.7": ["6.1.2"],
    "3.1": ["3.1.1"],
    "4.1": ["4.1.1"], "4.2": ["4.1.2"], "4.3": ["4.2.1"], "4.4": ["4.2.1", "4.2.2"],
    "6.1": ["7.1.1"], "6.2": ["7.1.1"], "6.3": ["7.2.1", "7.2.2"], "6.4": ["7.1.2"],
    "7.1": ["1.1.6"], "7.2.2": ["1.1.4"], "7.2.3": ["1.1.4"], "7.2.4": ["1.1.3", "1.1.4"],
    "7.2.8": ["10.1.1"], "7.2.9": ["10.1.1"], "7.2.10": ["10.1.1"],
    "7.3.1": ["1.1.4", "1.2.9"], "7.3.2": ["1.1.3", "1.1.4"], "7.3.3": ["1.1.6"], "7.3.4": ["1.1.6"],
    "9.1.1": ["8.1.1"], "9.1.3": ["8.2.2"], "9.1.6": ["8.1.1", "8.2.2"], "9.2.1": ["8.2.1"],
    "9.2.2": ["8.2.2"], "9.3.1": ["8.2.2"],
}

CORRISPONDENZE = {**DA_LIB, **DA_NL}


def rigenera(apps, schema_editor):
    Pericolo = apps.get_model("rischi", "Pericolo")
    SchedaModello = apps.get_model("rischi", "SchedaModello")
    SchedaAnalisi = apps.get_model("rischi", "SchedaAnalisi")

    nuovi_per_scheda = {}
    senza_corrispondenza = set()
    for Modello in (SchedaModello, SchedaAnalisi):
        legami = Modello.pericoli.through.objects.select_related("pericolo")
        for legame in legami:
            codice = legame.pericolo.codice
            if codice not in CORRISPONDENZE:
                senza_corrispondenza.add(codice)
                continue
            chiave = (Modello.__name__, legame.__dict__[f"{Modello.__name__.lower()}_id"])
            nuovi_per_scheda.setdefault(chiave, set()).update(CORRISPONDENZE[codice])

    Pericolo.objects.all().delete()
    per_codice = {codice: Pericolo.objects.create(codice=codice, descrizione=descr) for codice, descr in PERICOLI}

    for Modello in (SchedaModello, SchedaAnalisi):
        through = Modello.pericoli.through
        campo = f"{Modello.__name__.lower()}_id"
        through.objects.bulk_create([
            through(**{campo: pk, "pericolo_id": per_codice[c].pk})
            for (nome, pk), codici in nuovi_per_scheda.items() if nome == Modello.__name__
            for c in sorted(codici)
        ])
    if senza_corrispondenza:
        print(f"\n  Pericoli senza corrispondenza ISO 12100, tolti dalle schede: {', '.join(sorted(senza_corrispondenza))}")


class Migration(migrations.Migration):
    dependencies = [("rischi", "0013_codici_progressivi")]

    operations = [migrations.RunPython(rigenera, migrations.RunPython.noop)]
