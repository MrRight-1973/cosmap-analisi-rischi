"""Genera dati/Libreria_nuova_Cosmap.xlsx: libreria costruita da zero, senza la prima estrazione.

Fonti: Regolamento (UE) 2023/1230, Allegato III (requisiti RESS, testo pubblico);
EN ISO 12100 allegato B (solo come struttura dei tipi di pericolo, con parole nostre);
metodo ibrido dell'ISO/TR 14121-2 (scale e matrice). Le stime sono proposte da validare.

Uso:  python dati/genera_libreria_nuova.py
"""

from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

USCITA = Path(__file__).with_name("Libreria_nuova_Cosmap.xlsx")

# ---------------------------------------------------------------------------
# Requisiti RESS – Allegato III, parte 1
# (codice Direttiva 2006/42/CE o "—" se nuovo, titolo, codice Regolamento, novità, azione)
# ---------------------------------------------------------------------------

NOVITA_NESSUNA = "Nessuna modifica sostanziale nota: confrontare comunque il testo del Regolamento."

RESS = [
    ("1.1.1", "Definizioni", "1.1.1", "Aggiunte definizioni legate a comportamento autonomo ed evolutivo.", ""),
    ("1.1.2", "Principi d'integrazione della sicurezza", "1.1.2",
     "La valutazione considera anche i pericoli che possono nascere durante il ciclo di vita da un comportamento "
     "evolutivo o autonomo previsto della macchina.",
     "Chiedere sempre: la macchina ha funzioni che si modificano da sole (autoapprendimento, IA)?"),
    ("1.1.3", "Materiali e prodotti", "1.1.3", NOVITA_NESSUNA, ""),
    ("1.1.4", "Illuminazione", "1.1.4", NOVITA_NESSUNA, ""),
    ("1.1.5", "Progettazione della macchina ai fini della movimentazione", "1.1.5", NOVITA_NESSUNA, ""),
    ("1.1.6", "Ergonomia", "1.1.6",
     "Esteso allo stress psicologico dovuto all'interazione con la macchina e all'adattamento dell'interfaccia "
     "alle caratteristiche prevedibili degli operatori.", ""),
    ("1.1.7", "Posto di lavoro", "1.1.7", NOVITA_NESSUNA, ""),
    ("1.1.8", "Sedile", "1.1.8", NOVITA_NESSUNA, "Di regola non applicabile alle celle Cosmap (lavoro in piedi)."),
    ("—", "Protezione contro la corruzione", "1.1.9",
     "Nuovo: collegamenti a dispositivi esterni, hardware e software non devono poter portare la macchina in "
     "una situazione pericolosa; prove degli interventi sul software di sicurezza.",
     "Nuova scheda nel modulo Sistema di comando."),
    ("1.2.1", "Sicurezza e affidabilità dei sistemi di comando", "1.2.1",
     "Resistenza ad attacchi malevoli, registrazione degli interventi sul software di sicurezza, limiti alle "
     "azioni di macchine con comportamento autonomo.", ""),
    ("1.2.2", "Dispositivi di comando", "1.2.2", NOVITA_NESSUNA, ""),
    ("1.2.3", "Avviamento", "1.2.3", NOVITA_NESSUNA, ""),
    ("1.2.4.1", "Arresto normale", "1.2.4.1", NOVITA_NESSUNA, ""),
    ("1.2.4.2", "Arresto operativo", "1.2.4.2", NOVITA_NESSUNA, ""),
    ("1.2.4.3", "Arresto di emergenza", "1.2.4.3", NOVITA_NESSUNA, ""),
    ("1.2.4.4", "Insiemi di macchine", "1.2.4.4", NOVITA_NESSUNA, ""),
    ("1.2.5", "Selezione dei modi di comando o di funzionamento", "1.2.5", NOVITA_NESSUNA, ""),
    ("1.2.6", "Avaria del circuito di alimentazione di energia", "1.2.6", NOVITA_NESSUNA, ""),
    ("1.3.1", "Rischio di perdita di stabilità", "1.3.1", NOVITA_NESSUNA, ""),
    ("1.3.2", "Rischio di rottura durante il funzionamento", "1.3.2", NOVITA_NESSUNA, ""),
    ("1.3.3", "Rischi dovuti alla caduta o alla proiezione di oggetti", "1.3.3", NOVITA_NESSUNA, ""),
    ("1.3.4", "Rischi dovuti a superfici, spigoli o angoli", "1.3.4", NOVITA_NESSUNA, ""),
    ("1.3.5", "Rischi dovuti alle macchine combinate", "1.3.5", NOVITA_NESSUNA, ""),
    ("1.3.6", "Rischi dovuti alle variazioni delle condizioni di funzionamento", "1.3.6", NOVITA_NESSUNA, ""),
    ("1.3.7", "Rischi dovuti agli elementi mobili", "1.3.7",
     "Considerare anche il contatto previsto tra persone e macchina (applicazioni collaborative).", ""),
    ("1.3.8.1", "Elementi mobili di trasmissione", "1.3.8.1", NOVITA_NESSUNA, ""),
    ("1.3.8.2", "Elementi mobili che partecipano alla lavorazione", "1.3.8.2", NOVITA_NESSUNA, ""),
    ("1.3.9", "Rischi di movimenti non comandati", "1.3.9", NOVITA_NESSUNA, ""),
    ("1.4.1", "Ripari e dispositivi di protezione – requisiti generali", "1.4.1", NOVITA_NESSUNA, ""),
    ("1.4.2.1", "Ripari fissi", "1.4.2.1", NOVITA_NESSUNA, ""),
    ("1.4.2.2", "Ripari mobili interbloccati", "1.4.2.2", NOVITA_NESSUNA, ""),
    ("1.4.2.3", "Ripari regolabili che limitano l'accesso", "1.4.2.3", NOVITA_NESSUNA,
     "Di regola non applicabile (nessun riparo regolabile)."),
    ("1.4.3", "Requisiti particolari per i dispositivi di protezione", "1.4.3", NOVITA_NESSUNA, ""),
    ("1.5.1", "Alimentazione elettrica", "1.5.1", NOVITA_NESSUNA, ""),
    ("1.5.2", "Elettricità statica", "1.5.2", NOVITA_NESSUNA, ""),
    ("1.5.3", "Alimentazione con energia diversa dall'energia elettrica", "1.5.3", NOVITA_NESSUNA, ""),
    ("1.5.4", "Errori di montaggio", "1.5.4", NOVITA_NESSUNA, ""),
    ("1.5.5", "Temperature estreme", "1.5.5", NOVITA_NESSUNA, ""),
    ("1.5.6", "Incendio", "1.5.6", NOVITA_NESSUNA, ""),
    ("1.5.7", "Esplosione", "1.5.7", NOVITA_NESSUNA, ""),
    ("1.5.8", "Rumore", "1.5.8", NOVITA_NESSUNA, ""),
    ("1.5.9", "Vibrazioni", "1.5.9", NOVITA_NESSUNA,
     "Di regola non applicabile: macchina fissa, nessun utensile tenuto in mano."),
    ("1.5.10", "Radiazioni", "1.5.10", NOVITA_NESSUNA, "Di regola non applicabile."),
    ("1.5.11", "Radiazioni esterne", "1.5.11", NOVITA_NESSUNA, "Di regola non applicabile."),
    ("1.5.12", "Radiazioni laser", "1.5.12", NOVITA_NESSUNA, "Non applicabile se non ci sono laser (anche di misura)."),
    ("1.5.13", "Emissioni di materie e sostanze pericolose", "1.5.13", NOVITA_NESSUNA, ""),
    ("1.5.14", "Rischio di restare imprigionati in una macchina", "1.5.14", NOVITA_NESSUNA, ""),
    ("1.5.15", "Rischio di scivolamento, inciampo o caduta", "1.5.15", NOVITA_NESSUNA, ""),
    ("1.5.16", "Fulmine", "1.5.16", NOVITA_NESSUNA, "Di regola non applicabile (installazione al chiuso)."),
    ("1.6.1", "Manutenzione della macchina", "1.6.1", NOVITA_NESSUNA, ""),
    ("1.6.2", "Accesso ai posti di lavoro o ai punti d'intervento", "1.6.2", NOVITA_NESSUNA, ""),
    ("1.6.3", "Isolamento dalle fonti di energia", "1.6.3", NOVITA_NESSUNA, ""),
    ("1.6.4", "Intervento dell'operatore", "1.6.4", NOVITA_NESSUNA, ""),
    ("1.6.5", "Pulitura delle parti interne", "1.6.5", NOVITA_NESSUNA, ""),
    ("1.7.1.1", "Informazioni e dispositivi di informazione", "1.7.1.1", NOVITA_NESSUNA, ""),
    ("1.7.1.2", "Dispositivi di allarme", "1.7.1.2", NOVITA_NESSUNA, ""),
    ("1.7.2", "Avvertenza in merito ai rischi residui", "1.7.2", NOVITA_NESSUNA, ""),
    ("1.7.3", "Marcatura delle macchine", "1.7.3", NOVITA_NESSUNA, ""),
    ("1.7.4.1", "Principi generali di redazione delle istruzioni", "1.7.4.1",
     "Istruzioni anche solo in formato digitale, ma su richiesta al momento dell'acquisto vanno fornite "
     "gratuitamente su carta; le istruzioni di sicurezza essenziali restano su carta.",
     "Decidere il formato standard Cosmap (carta + digitale)."),
    ("1.7.4.2", "Contenuto delle istruzioni", "1.7.4.2", NOVITA_NESSUNA, ""),
    ("1.7.4.3", "Materiale promozionale", "1.7.4.3", NOVITA_NESSUNA, ""),
]

# ---------------------------------------------------------------------------
# Pericoli (tipi dell'EN ISO 12100 all. B, descritti con parole nostre)
# ---------------------------------------------------------------------------

PERICOLI = {
    "1.1": "Meccanico – schiacciamento",
    "1.2": "Meccanico – cesoiamento",
    "1.3": "Meccanico – taglio",
    "1.4": "Meccanico – trascinamento o intrappolamento",
    "1.5": "Meccanico – impigliamento",
    "1.6": "Meccanico – urto",
    "1.7": "Meccanico – abrasione o attrito",
    "1.8": "Meccanico – perforazione o puntura",
    "1.9": "Meccanico – proiezione di oggetti o frammenti",
    "1.10": "Meccanico – caduta di oggetti o perdita di stabilità",
    "1.11": "Meccanico – fluidi in pressione",
    "1.12": "Meccanico – movimento o avviamento inatteso",
    "2.1": "Elettrico – contatto diretto con parti attive",
    "2.2": "Elettrico – contatto indiretto (parti in tensione per guasto)",
    "2.3": "Elettrico – fenomeni elettrostatici",
    "2.4": "Elettrico – cortocircuito o sovraccarico con innesco di incendio",
    "3.1": "Termico – contatto con superfici o pezzi caldi",
    "3.2": "Termico – incendio",
    "4.1": "Rumore – esposizione con danno all'udito",
    "4.2": "Rumore – mancata percezione di segnali e comunicazioni",
    "7.1": "Sostanze – inalazione di polveri (metalli, abrasivi, fibre)",
    "7.2": "Sostanze – contatto con prodotti (paste abrasive, oli, residui)",
    "7.3": "Sostanze – esplosione di polveri",
    "7.4": "Sostanze – inalazione di nebbie o vapori",
    "8.1": "Ergonomia – postura scorretta o movimenti ripetitivi",
    "8.2": "Ergonomia – movimentazione manuale di carichi",
    "8.3": "Ergonomia – illuminazione o visibilità inadeguata",
    "8.4": "Ergonomia – errore umano su comandi e segnali",
    "9.1": "Ambiente – scivolamento o inciampo",
    "9.2": "Ambiente – caduta dall'alto",
    "9.3": "Ambiente – persona chiusa all'interno della macchina",
    "10.1": "Combinazione – interazione tra le parti di un insieme",
    "10.2": "Combinazione – guasto o avaria del sistema di comando",
    "10.3": "Combinazione – manomissione o corruzione del software",
}

# ---------------------------------------------------------------------------
# Norme (codice, edizione di riferimento, oggetto, edizione più recente nota, nota)
# ---------------------------------------------------------------------------

DA_VERIFICARE = "Edizione e stato di armonizzazione da verificare sulla GUUE prima dell'uso."

NORME = [
    ("EN ISO 12100", "2010", "Principi generali di progettazione – valutazione e riduzione del rischio", "2010", ""),
    ("ISO/TR 14121-2", "2012", "Valutazione del rischio – guida pratica ed esempi di metodi", "2012", "Rapporto tecnico, non armonizzato."),
    ("EN ISO 13849-1", "2023", "Parti dei sistemi di comando legate alla sicurezza – principi di progettazione", "2023", DA_VERIFICARE),
    ("EN ISO 13849-2", "2012", "Parti dei sistemi di comando legate alla sicurezza – validazione", "2012", ""),
    ("EN IEC 62061", "2021", "Sicurezza funzionale dei sistemi di comando legati alla sicurezza", "2021", DA_VERIFICARE),
    ("EN 60204-1", "2018", "Equipaggiamento elettrico delle macchine – regole generali", "2018", DA_VERIFICARE),
    ("EN IEC 61439-1", "2021", "Quadri elettrici di bassa tensione – regole generali", "2021", "Norma della Direttiva bassa tensione."),
    ("EN ISO 13850", "2015", "Funzione di arresto di emergenza", "2015", ""),
    ("EN ISO 14118", "2018", "Prevenzione dell'avviamento inatteso", "2018", ""),
    ("EN ISO 14119", "2013", "Dispositivi di interblocco associati ai ripari", "2024", "Pubblicata ISO 14119:2024: " + DA_VERIFICARE),
    ("EN ISO 14120", "2015", "Ripari – requisiti generali per progettazione e costruzione", "2015", ""),
    ("EN ISO 13857", "2019", "Distanze di sicurezza per impedire il raggiungimento delle zone pericolose", "2019", ""),
    ("EN ISO 13854", "2019", "Spazi minimi per evitare lo schiacciamento di parti del corpo", "2019", ""),
    ("EN ISO 13855", "2010", "Posizionamento dei mezzi di protezione rispetto alla velocità di avvicinamento", "2024", "Pubblicata ISO 13855:2024: " + DA_VERIFICARE),
    ("EN IEC 61496-1", "2020", "Apparecchi elettrosensibili di protezione – requisiti generali", "2020", ""),
    ("EN ISO 10218-1", "2025", "Robot industriali – requisiti per i robot", "2025", DA_VERIFICARE),
    ("EN ISO 10218-2", "2025", "Robot industriali – applicazioni e celle robotizzate", "2025", DA_VERIFICARE),
    ("EN ISO 11161", "2007+A1:2010", "Sistemi di fabbricazione integrati", "2007+A1:2010", ""),
    ("EN ISO 16089", "2015", "Macchine utensili – rettificatrici fisse", "2015",
     "Verificare se il campo di applicazione copre smerigliatrici a nastro e lucidatrici Cosmap."),
    ("EN 13743", "2009", "Prodotti abrasivi rivestiti (nastri) – requisiti di sicurezza", "2009", DA_VERIFICARE),
    ("EN ISO 4414", "2010", "Pneumatica – regole generali e requisiti di sicurezza", "2010", ""),
    ("EN ISO 14122-2", "2016", "Mezzi di accesso permanenti – piattaforme e passerelle", "2016", ""),
    ("EN ISO 14122-3", "2016", "Mezzi di accesso permanenti – scale, scale a castello e parapetti", "2016", ""),
    ("EN 1837", "2020", "Illuminazione integrata alle macchine", "2020", ""),
    ("EN 614-1", "2006+A1:2009", "Principi ergonomici di progettazione – terminologia e principi generali", "2006+A1:2009", ""),
    ("EN 1005-2", "2003+A1:2008", "Prestazione fisica umana – movimentazione manuale di macchine e componenti", "2003+A1:2008", ""),
    ("EN ISO 14738", "2008", "Requisiti antropometrici per i posti di lavoro alle macchine", "2008", ""),
    ("EN 61310-1", "2008", "Indicazione, marcatura e manovra – segnali visivi, acustici e tattili", "2008", ""),
    ("EN ISO 7010", "2020", "Segni grafici – colori e segnali di sicurezza registrati", "2020", ""),
    ("EN ISO 20607", "2019", "Manuale di istruzioni – principi generali di stesura", "2019", ""),
    ("EN ISO 11688-1", "2009", "Progettazione di macchine a bassa rumorosità – pianificazione", "2009", ""),
    ("EN ISO 3744", "2010", "Determinazione dei livelli di potenza sonora – metodo tecnico progettuale", "2010", ""),
    ("EN ISO 11202", "2010", "Livelli di pressione sonora al posto di lavoro", "2010", ""),
    ("EN ISO 4871", "2009", "Dichiarazione e verifica dei valori di emissione sonora", "2009", ""),
    ("EN ISO 13732-1", "2008", "Ergonomia degli ambienti termici – superfici calde", "2008", ""),
    ("EN ISO 19353", "2019", "Prevenzione e protezione contro l'incendio", "2019", ""),
    ("EN 1127-1", "2019", "Atmosfere esplosive – prevenzione dell'esplosione e protezione", "2019", ""),
    ("EN ISO 14123-1", "2015", "Riduzione dei rischi per la salute da sostanze pericolose emesse", "2015", ""),
    ("EN IEC 62443-3-3", "2019", "Sicurezza informatica dei sistemi di automazione industriale", "2019",
     "Non armonizzata per le macchine: riferimento utile per il RESS 1.1.9."),
]

# Armonizzate secondo la Direttiva 2006/42/CE, in attesa delle citazioni per il Regolamento:
# da verificare sulla GUUE. Tipo A/B/C come nella EN ISO 12100.
NON_ARMONIZZATE = {"ISO/TR 14121-2", "EN IEC 61439-1", "EN ISO 7010", "EN IEC 62443-3-3", "EN ISO 10218-1", "EN ISO 10218-2"}
NORME_A = {"EN ISO 12100", "ISO/TR 14121-2"}
NORME_C = {"EN ISO 10218-1", "EN ISO 10218-2", "EN ISO 16089", "EN 13743"}


def tipo_norma(codice):
    return "A" if codice in NORME_A else "C" if codice in NORME_C else "B"


def codice_pericolo(codice):
    """'7.1' -> '7.01': codici distinti da quelli della prima estrazione già presenti nei database."""
    gruppo, voce = codice.split(".")
    return f"{gruppo}.{int(voce):02d}"


# ---------------------------------------------------------------------------
# Metodo ibrido ISO/TR 14121-2 (scale e matrice)
# ---------------------------------------------------------------------------

FASCE = [(3, 4), (5, 7), (8, 10), (11, 13), (14, 15)]
MATRICE = {  # Se -> esito per fascia di Cl
    4: ["Suggerite", "Richieste", "Richieste", "Richieste", "Richieste"],
    3: ["OK", "Suggerite", "Richieste", "Richieste", "Richieste"],
    2: ["OK", "OK", "Suggerite", "Richieste", "Richieste"],
    1: ["OK", "OK", "OK", "Suggerite", "Richieste"],
}
SCALE = {
    "Se – Gravità": [
        (4, "Irreversibile grave: morte, perdita di un occhio o di un arto"),
        (3, "Permanente: perdita di dita, lesioni con esiti permanenti"),
        (2, "Reversibile con cure mediche"),
        (1, "Reversibile con primo soccorso"),
    ],
    "Fr – Frequenza e durata dell'esposizione": [
        (5, "Più di una volta all'ora"),
        (5, "Da una volta all'ora a una volta al giorno (un livello in meno se ogni esposizione dura meno di 10 min)"),
        (4, "Da una volta al giorno a una volta ogni due settimane"),
        (3, "Da una volta ogni due settimane a una volta all'anno"),
        (2, "Meno di una volta all'anno"),
    ],
    "Pr – Probabilità dell'evento pericoloso": [
        (5, "Molto alta"),
        (4, "Probabile"),
        (3, "Possibile"),
        (2, "Rara"),
        (1, "Trascurabile"),
    ],
    "Av – Possibilità di evitare o limitare il danno": [
        (5, "Impossibile"),
        (3, "Possibile"),
        (1, "Probabile"),
    ],
}
NOMI_SE = {4: "Irreversibile grave", 3: "Permanente", 2: "Reversibile con cure mediche", 1: "Reversibile con primo soccorso"}


def esito(stima):
    if not stima:
        return None, None
    se, fr, pr, av = stima
    cl = fr + pr + av
    fascia = next(i for i, (lo, hi) in enumerate(FASCE) if lo <= cl <= hi)
    return cl, MATRICE[se][fascia]


# ---------------------------------------------------------------------------
# Moduli
# ---------------------------------------------------------------------------

GEN, CMD, CAB, TAV, ZSM, PAL, GSM, TRA, ZPU, LUC, ELE, PNE, PAS, INF = (
    "Generale impianto",
    "Sistema di comando",
    "Cabina di protezione e ripari",
    "Tavola rotante – carico/scarico",
    "Zona smerigliatura - generale",
    "Stazione di carico a doppio pallet",
    "Gruppo di smerigliatura (robot + smerigliatrici a nastro)",
    "Trasportatore a tappeto di scarico",
    "Zona pulitura – generale",
    "Unità di lucidatura CNC",
    "Equipaggiamento elettrico",
    "Equipaggiamento pneumatico",
    "Impianto pasta abrasiva",
    "Informazioni, marcatura e istruzioni",
)

MODULI = [
    (GEN, "Sempre", "Requisiti validi per ogni impianto: materiali, stabilità, ergonomia, illuminazione, rumore, manutenzione."),
    (PAS, "Se presente impianto di distribuzione della pasta abrasiva", "Serbatoio, pompa, tubazioni e ugelli della pasta."),
    (CMD, "Sempre", "Logica di sicurezza, comandi, arresti, modi di funzionamento, software."),
    (CAB, "Se presente cabina chiusa con porte di accesso", "Ripari perimetrali fissi e porte interbloccate della cella."),
    (TAV, "Se presente tavola rotante con carico/scarico manuale", "Postazione manuale, rotazione tavola, pinze porta-pezzo."),
    (ZSM, "Se presente zona di smerigliatura", "Polveri metalliche e abrasive, scintille, incendio, pulizia della zona."),
    (PAL, "Se presente stazione di carico a pallet", "Doppio pallet con scambio automatico e protezione della zona di carico."),
    (GSM, "Se presente robot con smerigliatrici a nastro", "Robot che porta il pezzo sulle smerigliatrici a nastro."),
    (TRA, "Se presente trasportatore di scarico", "Nastro a tappeto per l'uscita dei pezzi."),
    (ZPU, "Se presente zona di pulitura/lucidatura", "Polveri e fibre di lucidatura, pasta, incendio, pulizia della zona."),
    (LUC, "Se presente unità di lucidatura CNC", "Unità con dischi o spazzole in rotazione e assi CNC."),
    (ELE, "Sempre", "Quadro e impianto elettrico."),
    (PNE, "Se presente impianto pneumatico", "Gruppo di trattamento aria, valvole, attuatori."),
    (INF, "Sempre", "Avvertenze, segnali, marcatura, manuale di istruzioni."),
]
# Sigla del modulo: prima parte dei codici delle schede (GEN-01, GEN-02, ...)
SIGLE = {GEN: "GEN", PAS: "PAS", CMD: "CMD", CAB: "CAB", TAV: "TAV", ZSM: "ZSM", PAL: "PAL",
         GSM: "ROB", TRA: "TRA", ZPU: "ZPU", LUC: "LUC", ELE: "ELE", PNE: "PNE", INF: "INF"}

# ---------------------------------------------------------------------------
# Schede
# ---------------------------------------------------------------------------

TUTTE = "Tutte."
NORM = "Normale."
MANUT = "Manutenzione; pulizia."


def S(modulo, zona, ress, zona_pericolosa, condizioni, pericoli, iniziale, misure, istruzioni, finale,
      A=("EN ISO 12100",), B=(), C=(), nota=""):
    return dict(
        modulo=modulo, zona=zona, ress=ress, zp=zona_pericolosa, cond=condizioni, per=pericoli,
        si=iniziale, mis=misure, istr=istruzioni, sf=finale, A=A, B=B, C=C, nota=nota,
    )


DESCRITTIVA = "Scheda descrittiva, senza stima del rischio."

SCHEDE = [
    # ---------------- Generale impianto ----------------
    S(GEN, "Impianto", "1.1.1", "", TUTTE, [], None,
      [("INFO", "Il manuale riporta le definizioni usate: zona pericolosa, persona esposta, operatore, personale "
                "qualificato per manutenzione meccanica ed elettrica.", "EN ISO 20607")],
      "Nel manuale: capitolo definizioni e qualifiche del personale.", None, B=("EN ISO 20607",), nota=DESCRITTIVA),
    S(GEN, "Impianto", "1.1.2", "", TUTTE, [], None,
      [("PROG", "La riduzione del rischio segue l'ordine: progettazione intrinsecamente sicura, protezioni, informazioni.", "EN ISO 12100"),
       ("PROG", "La valutazione considera uso previsto e uso scorretto ragionevolmente prevedibile in tutte le fasi di vita.", None),
       ("PROG", "Verificato che l'impianto non ha comportamento evolutivo o autonomo; se presente, valutarlo a parte.", None),
       ("INFO", "Il manuale descrive uso previsto, usi non consentiti e limiti dell'impianto (pezzi, materiali, dimensioni).", None)],
      "Nel manuale: uso previsto, uso scorretto prevedibile, limiti.", None, B=(), nota=DESCRITTIVA),
    S(GEN, "Impianto", "1.1.3", "Parti dell'impianto a contatto con operatori e pezzi", NORM, ["7.2"], (2, 3, 2, 3),
      [("PROG", "Materiali costruttivi scelti senza sostanze pericolose note (amianto, vernici al piombo).", None),
       ("PROG", "Materiali compatibili con paste, oli e detergenti indicati per l'uso.", None),
       ("INFO", "Il manuale elenca i prodotti ammessi e chiede di consultare le schede di sicurezza.", None)],
      "Usare solo i prodotti indicati; consultare le schede di sicurezza dei prodotti di consumo.", (2, 3, 1, 3)),
    S(GEN, "Impianto", "1.1.4", "Zone di lavoro, regolazione e manutenzione", "Normale; regolazione / attrezzamento; manutenzione.",
      ["8.3"], (2, 5, 2, 3),
      [("PROG", "Illuminazione interna della cella, adeguata alle operazioni di controllo e manutenzione.", "EN 1837"),
       ("INFO", "Il manuale indica l'illuminazione ambiente necessaria nel locale di installazione (a cura del cliente).", None)],
      "Garantire nel locale l'illuminazione indicata nel manuale.", (2, 5, 1, 1), B=("EN 1837",)),
    S(GEN, "Impianto", "1.1.5", "Gruppi dell'impianto durante sollevamento e trasporto", "Trasporto; installazione; smantellamento.",
      ["1.10", "1.1"], (3, 2, 3, 3),
      [("PROG", "Punti di sollevamento (golfari, passaggi per forche) dimensionati e indicati.", None),
       ("PROT", "Parti mobili bloccate per il trasporto con fermi rimovibili segnalati.", None),
       ("INFO", "Masse, baricentro e schema di sollevamento indicati sui gruppi e nel manuale.", None)],
      "Sollevare solo dai punti indicati, con mezzi di portata adeguata, da personale abilitato.", (3, 2, 1, 1)),
    S(GEN, "Impianto", "1.1.6", "Pannello operatore e postazioni di comando", NORM, ["8.4", "8.1"], (2, 5, 2, 3),
      [("PROG", "Pannello operatore ad altezza e orientamento ergonomici; schermate in lingua, con messaggi chiari.", "EN 614-1"),
       ("PROG", "Ritmo di lavoro determinato dall'operatore, non imposto dalla macchina.", None),
       ("INFO", "Il manuale descrive le postazioni e le operazioni dell'operatore.", None)],
      "", (2, 5, 1, 1), B=("EN 614-1", "EN ISO 14738")),
    S(GEN, "Impianto", "1.1.7", "Postazioni dell'operatore", NORM, [], None,
      [("PROG", "Postazioni di lavoro definite: pannello operatore, zona di carico e scarico; nessuna postazione all'interno della cella.", None),
       ("INFO", "Il manuale indica le postazioni e lo spazio libero da lasciare attorno all'impianto.", None)],
      "Nel manuale: postazioni e spazi di rispetto.", None, nota=DESCRITTIVA),
    S(GEN, "Impianto", "1.3.1", "Struttura dell'impianto", "Installazione; normale.", ["1.10"], (3, 2, 3, 3),
      [("PROG", "Struttura verificata per stabilità; gruppi ancorati al pavimento con tasselli.", None),
       ("INFO", "Il manuale indica caratteristiche del pavimento e modalità di ancoraggio.", None)],
      "Ancorare l'impianto come indicato nel manuale prima della messa in servizio.", (3, 2, 1, 1)),
    S(GEN, "Impianto", "1.3.4", "Lamiere, profili e carter", "Normale; manutenzione.", ["1.3"], (2, 4, 2, 3),
      [("PROG", "Bordi delle lamiere rifilati o ripiegati; spigoli accessibili arrotondati; profili chiusi con tappi.", None)],
      "", (2, 4, 1, 1)),
    S(GEN, "Impianto", "1.3.5", "Zone di lavoro diverse dello stesso impianto", "Normale; manutenzione; sblocco anomalie.",
      ["10.1", "1.12"], (3, 3, 3, 3),
      [("PROG", "Ogni zona può essere arrestata e messa in sicurezza separatamente, senza fermare le altre se non necessario.", None),
       ("PROT", "L'accesso a una zona arresta i movimenti pericolosi di quella zona e di quelle raggiungibili da lì.", "EN ISO 11161"),
       ("INFO", "Il manuale descrive le zone e quali movimenti si fermano con ogni accesso.", None)],
      "Prima di entrare in una zona verificare sul pannello che sia ferma.", (3, 2, 1, 1), B=("EN ISO 11161",)),
    S(GEN, "Impianto", "1.5.4", "Collegamenti elettrici e pneumatici tra i gruppi", "Installazione; manutenzione.", ["1.12", "2.2"], (3, 2, 3, 3),
      [("PROG", "Connettori codificati o non intercambiabili tra i gruppi; tubi e cavi numerati come negli schemi.", None),
       ("INFO", "Schemi e istruzioni di montaggio con le marcature dei collegamenti.", None)],
      "Montaggio e collegamenti solo da personale qualificato seguendo gli schemi.", (3, 2, 1, 1)),
    S(GEN, "Impianto", "1.5.8", "Posto dell'operatore", NORM, ["4.1", "4.2"], (2, 5, 3, 3),
      [("PROG", "Sorgenti di rumore ridotte in progetto: motori e aspirazione scelti a bassa rumorosità, silenziatori sugli scarichi.", "EN ISO 11688-1"),
       ("PROT", "Cabina chiusa con pannelli fonoassorbenti.", None),
       ("INFO", "Valori di emissione sonora misurati e dichiarati nel manuale; indicazione sui DPI se necessari.", "EN ISO 4871")],
      "Il manuale riporta i valori di rumore misurati; usare protettori auricolari se indicato.", (2, 5, 1, 1),
      B=("EN ISO 11688-1", "EN ISO 3744", "EN ISO 11202", "EN ISO 4871"),
      nota="Valori da misurare sul primo impianto della serie."),
    S(GEN, "Impianto", "1.5.15", "Pavimento attorno all'impianto e zone di accesso", "Normale; manutenzione; pulizia.", ["9.1"], (2, 4, 3, 3),
      [("PROG", "Nessun cavo o tubo a pavimento nelle vie di passaggio: canaline aeree o a pavimento carrabili.", None),
       ("PROG", "Vasche di raccolta sotto i punti di possibile gocciolamento.", None),
       ("INFO", "Il manuale chiede di tenere pulito il pavimento da pasta, olio e polveri.", None)],
      "Pulire subito perdite di pasta o olio a pavimento.", (2, 4, 1, 1)),
    S(GEN, "Impianto", "1.6.1", "Punti di manutenzione", "Manutenzione.", ["1.12"], (3, 3, 3, 3),
      [("PROG", "Punti di regolazione, lubrificazione e manutenzione posti fuori dalle zone pericolose dove possibile.", None),
       ("PROT", "Interventi all'interno solo a macchina ferma e con energie isolate.", "EN ISO 14118"),
       ("INFO", "Piano di manutenzione con frequenze, qualifiche richieste e procedure di messa in sicurezza.", None)],
      "Eseguire la manutenzione secondo il piano del manuale, a energie isolate.", (3, 3, 1, 1), B=("EN ISO 14118",)),
    S(GEN, "Impianto", "1.6.2", "Parti alte dell'impianto (motori aspirazione, carter superiori)", "Manutenzione.", ["9.2"], (3, 3, 3, 3),
      [("PROG", "Componenti da manutenere spesso raggiungibili da terra.", None),
       ("PROT", "Dove serve accedere in quota: piattaforma o scala fissa con parapetti.", "EN ISO 14122-2"),
       ("INFO", "Per gli interventi occasionali in quota il manuale indica i mezzi da usare.", None)],
      "Per interventi in quota usare i mezzi indicati nel manuale.", (3, 3, 1, 1), B=("EN ISO 14122-2", "EN ISO 14122-3")),
    S(GEN, "Impianto", "1.6.4", "Interventi dell'operatore", "Regolazione / attrezzamento; sblocco anomalie.", [], None,
      [("PROG", "Le operazioni dell'operatore (avvio ciclo, cambio articolo, reset allarmi) si fanno dall'esterno della cella.", None),
       ("INFO", "Il manuale distingue le operazioni dell'operatore da quelle del personale di manutenzione.", None)],
      "Nel manuale: chi può fare cosa.", None, nota=DESCRITTIVA),

    # ---------------- Sistema di comando ----------------
    S(CMD, "Sistema di comando", "1.1.9", "PLC, robot, pannello e collegamenti di rete", TUTTE, ["10.3", "1.12"], (4, 3, 2, 3),
      [("PROG", "Funzioni di sicurezza su PLC/relè di sicurezza separati dalla logica di processo e non modificabili da rete.", "EN ISO 13849-1"),
       ("PROT", "Accesso ai programmi e ai parametri di sicurezza protetto da password per livello; porte di rete non usate disattivate.", "EN IEC 62443-3-3"),
       ("PROT", "Checksum o firma dei programmi di sicurezza registrata al collaudo; modifiche tracciate.", None),
       ("INFO", "Il manuale indica come gestire password, teleassistenza e aggiornamenti software.", None)],
      "Non collegare l'impianto a reti aperte senza protezione; conservare le password con cura.", (4, 2, 1, 1),
      B=("EN ISO 13849-1", "EN IEC 62443-3-3"), nota="Nuovo requisito del Regolamento: verificare le scelte con il fornitore del PLC."),
    S(CMD, "Sistema di comando", "1.2.1", "Funzioni di sicurezza dell'impianto", TUTTE, ["10.2", "1.12"], (4, 3, 3, 3),
      [("PROG", "Funzioni di sicurezza elencate con il PL richiesto, progettate e validate.", "EN ISO 13849-1"),
       ("PROG", "Validazione documentata delle funzioni di sicurezza.", "EN ISO 13849-2"),
       ("PROT", "Registrazione degli interventi sul software di sicurezza (versione, data, autore).", None)],
      "", (4, 2, 1, 1), B=("EN ISO 13849-1", "EN ISO 13849-2", "EN IEC 62061")),
    S(CMD, "Sistema di comando", "1.2.2", "Pulsantiere e pannello operatore", NORM, ["8.4"], (3, 5, 2, 3),
      [("PROG", "Comandi visibili, identificati da simboli o testi, disposti in modo da evitare azionamenti involontari.", "EN 60204-1"),
       ("PROG", "Comandi di avvio ciclo posti in punti da cui si vede la zona di lavoro.", None),
       ("INFO", "Il manuale descrive ogni comando del pannello.", None)],
      "", (3, 5, 1, 1), B=("EN 60204-1", "EN 61310-1")),
    S(CMD, "Sistema di comando", "1.2.3", "Intero impianto", "Normale; regolazione / attrezzamento.", ["1.12"], (4, 4, 2, 3),
      [("PROG", "Avvio solo con azione volontaria su un comando previsto; chiusura di un riparo o reset non avviano la macchina.", "EN ISO 14118"),
       ("PROG", "Segnale acustico/luminoso prima dell'avvio se dalla postazione non si vede tutta la zona.", None)],
      "", (4, 2, 1, 1), B=("EN ISO 14118",)),
    S(CMD, "Sistema di comando", "1.2.4.1", "Intero impianto", NORM, ["1.12"], (3, 4, 2, 3),
      [("PROG", "Comando di arresto completo di ogni zona, prioritario sui comandi di avvio.", "EN 60204-1")],
      "", (3, 4, 1, 1), B=("EN 60204-1",)),
    S(CMD, "Sistema di comando", "1.2.4.2", "Zone con arresto operativo controllato", "Normale; regolazione / attrezzamento.", ["1.12"], (4, 4, 2, 3),
      [("PROG", "Durante gli arresti operativi (attesa pezzo, cambio pallet) la condizione di arresto è sorvegliata.", "EN ISO 13849-1"),
       ("PROT", "L'accesso alla zona è comunque interbloccato: l'arresto operativo non sostituisce i ripari.", None)],
      "", (4, 2, 1, 1), B=("EN ISO 13849-1",)),
    S(CMD, "Sistema di comando", "1.2.4.3", "Pulsanti di emergenza", TUTTE, ["1.12", "1.1"], (4, 4, 3, 3),
      [("PROG", "Pulsanti di emergenza sul pannello, presso ogni porta e nella zona di carico; arresto di categoria 0 o 1.", "EN ISO 13850"),
       ("PROG", "Il ripristino dell'emergenza non riavvia la macchina.", None)],
      "", (4, 2, 1, 1), B=("EN ISO 13850", "EN 60204-1")),
    S(CMD, "Sistema di comando", "1.2.4.4", "Collegamento con altre macchine o con la linea del cliente", "Normale; installazione.", ["10.1"], (4, 3, 2, 3),
      [("PROG", "Emergenze e arresti collegati con le macchine adiacenti secondo lo schema concordato.", "EN ISO 11161"),
       ("INFO", "Il manuale indica i segnali di interfaccia disponibili e i limiti del collegamento.", None)],
      "Collegamenti a macchine di altri fornitori da definire con Cosmap.", (4, 2, 1, 1), B=("EN ISO 11161",),
      nota="Valutare caso per caso quando l'impianto entra in un insieme."),
    S(CMD, "Sistema di comando", "1.2.5", "Selettore dei modi di funzionamento", "Regolazione / attrezzamento; programmazione; manutenzione.",
      ["1.12", "1.6"], (4, 3, 3, 3),
      [("PROG", "Selettore a chiave o accesso con password per i modi diversi dal ciclo automatico.", "EN 60204-1"),
       ("PROT", "In modo manuale con porta aperta: velocità ridotta e comando ad azione mantenuta o dispositivo di abilitazione.", "EN ISO 10218-1"),
       ("INFO", "Il manuale descrive ogni modo e chi può usarlo.", None)],
      "Modi manuali solo per personale addestrato e autorizzato.", (3, 3, 1, 1), B=("EN 60204-1",), C=("EN ISO 10218-1",)),
    S(CMD, "Sistema di comando", "1.2.6", "Intero impianto", TUTTE, ["1.12", "1.10"], (4, 2, 3, 3),
      [("PROG", "Al ritorno dell'energia l'impianto non riparte da solo.", "EN 60204-1"),
       ("PROG", "Pinze e bloccaggi mantengono il pezzo in caso di mancanza di aria o tensione (valvole bistabili o ritegno).", None)],
      "", (4, 2, 1, 1), B=("EN 60204-1", "EN ISO 4414")),

    # ---------------- Cabina di protezione e ripari ----------------
    S(CAB, "Cabina", "1.3.7", "Interno della cella", "Normale; regolazione / attrezzamento; manutenzione.", ["1.1", "1.6"], (4, 4, 3, 3),
      [("PROT", "Cella chiusa da ripari perimetrali; elementi mobili raggiungibili solo aprendo porte interbloccate.", "EN ISO 14120"),
       ("PROT", "Altezza e distanza dei ripari tali da non raggiungere le zone pericolose.", "EN ISO 13857")],
      "", (4, 2, 1, 1), B=("EN ISO 14120", "EN ISO 13857")),
    S(CAB, "Cabina", "1.4.1", "Ripari della cella", TUTTE, [], None,
      [("PROT", "Ripari robusti, fissati stabilmente, che non creano pericoli aggiuntivi e non si possono eludere facilmente.", "EN ISO 14120"),
       ("PROT", "Pannelli trasparenti dove serve vedere la lavorazione, in materiale resistente agli urti.", None)],
      "", None, B=("EN ISO 14120",), nota=DESCRITTIVA),
    S(CAB, "Cabina", "1.4.2.1", "Pannelli fissi della cabina", "Normale; manutenzione.", ["1.1", "1.6"], (4, 3, 2, 3),
      [("PROT", "Pannelli fissi rimovibili solo con attrezzo; viti imperdibili sui pannelli smontati per manutenzione.", "EN ISO 14120")],
      "", (4, 2, 1, 1), B=("EN ISO 14120",)),
    S(CAB, "Cabina", "1.4.2.2", "Porte di accesso alla cella", "Regolazione / attrezzamento; manutenzione; sblocco anomalie.", ["1.1", "1.6", "1.12"], (4, 4, 3, 3),
      [("PROT", "Porte con dispositivo di interblocco con bloccaggio: apertura solo a movimenti fermi.", "EN ISO 14119"),
       ("PROT", "Funzione di interblocco con PL adeguato alla valutazione.", "EN ISO 13849-1"),
       ("PROT", "Dispositivi difficili da eludere (codifica alta o montaggio protetto).", None)],
      "", (4, 2, 1, 1), B=("EN ISO 14119", "EN ISO 13849-1")),
    S(CAB, "Cabina", "1.4.3", "Barriere e dispositivi di protezione della cella", "Normale.", ["1.1", "1.6"], (4, 4, 3, 3),
      [("PROT", "Dispositivi elettrosensibili (barriere, scanner) del tipo adeguato, posizionati secondo il tempo di arresto.", "EN ISO 13855"),
       ("PROT", "Il ripristino dopo l'intervento del dispositivo richiede un comando volontario dall'esterno.", None)],
      "", (4, 2, 1, 1), B=("EN ISO 13855", "EN IEC 61496-1")),
    S(CAB, "Cabina", "1.3.3", "Pareti della cabina verso l'esterno", NORM, ["1.9"], (3, 5, 2, 3),
      [("PROT", "Ripari e pannelli trasparenti scelti per trattenere pezzi o frammenti proiettati.", "EN ISO 14120")],
      "", (3, 5, 1, 1), B=("EN ISO 14120",)),
    S(CAB, "Cabina", "1.5.14", "Interno della cella", "Manutenzione; sblocco anomalie.", ["9.3", "1.12"], (4, 3, 2, 3),
      [("PROT", "Porte apribili sempre dall'interno senza attrezzi; sblocco di fuga sul dispositivo di interblocco.", "EN ISO 14119"),
       ("PROT", "Chi entra porta con sé la chiave o il lucchetto che impedisce il riavvio.", None),
       ("INFO", "Il manuale descrive la procedura di accesso alla cella.", None)],
      "Entrare nella cella solo con la procedura del manuale.", (4, 2, 1, 1), B=("EN ISO 14119",)),

    # ---------------- Tavola rotante ----------------
    S(TAV, "Zona di carico", "1.3.8.2", "Tavola rotante e struttura fissa durante la rotazione", NORM, ["1.1", "1.2"], (3, 5, 3, 3),
      [("PROT", "Divisorio sulla tavola che separa la postazione di carico dalla zona di lavoro.", "EN ISO 14120"),
       ("PROT", "Rotazione solo con zona di carico libera, sorvegliata da barriera o pedana.", "EN ISO 13855"),
       ("PROG", "Spazi tra parti in movimento e struttura fissa non inferiori ai minimi.", "EN ISO 13854")],
      "", (3, 5, 1, 1), B=("EN ISO 14120", "EN ISO 13855", "EN ISO 13854")),
    S(TAV, "Zona di carico", "1.4.3", "Accesso alla tavola dalla postazione di carico", NORM, ["1.1", "1.6"], (3, 5, 3, 3),
      [("PROT", "Dispositivo elettrosensibile o pedana sensibile che impedisce la rotazione con l'operatore nella zona.", "EN IEC 61496-1"),
       ("PROT", "Posizione del dispositivo calcolata con il tempo di arresto della tavola.", "EN ISO 13855")],
      "", (3, 5, 1, 1), B=("EN IEC 61496-1", "EN ISO 13855")),
    S(TAV, "Zona di carico", "1.1.6", "Postazione di carico e scarico manuale", NORM, ["8.1", "8.2"], (2, 5, 3, 3),
      [("PROG", "Altezza di carico tra 900 e 1100 mm circa; pinze raggiungibili senza sporgersi.", "EN 1005-2"),
       ("INFO", "Il manuale indica i pesi massimi dei pezzi da movimentare a mano.", None)],
      "Rispettare pesi e posture indicati nel manuale.", (2, 5, 1, 1), B=("EN 1005-2", "EN 614-1")),
    S(TAV, "Zona di carico", "1.3.9", "Pinze porta-pezzo", NORM, ["1.10", "1.1"], (2, 5, 2, 3),
      [("PROG", "Pinze che mantengono il pezzo anche senza aria (molla o valvola di ritegno).", "EN ISO 4414"),
       ("PROG", "Apertura delle pinze solo con comando dell'operatore a tavola ferma.", None)],
      "", (2, 5, 1, 1), B=("EN ISO 4414",)),
    S(TAV, "Zona di carico", "1.5.5", "Pezzi lavorati allo scarico", NORM, ["3.1"], (2, 5, 3, 3),
      [("PROG", "Tempo tra fine lavorazione e scarico sufficiente a ridurre la temperatura del pezzo.", None),
       ("INFO", "Il manuale indica i guanti da usare per lo scarico.", "EN ISO 13732-1")],
      "Usare guanti di protezione per maneggiare i pezzi appena lavorati.", (2, 5, 1, 3), B=("EN ISO 13732-1",)),

    # ---------------- Zona smerigliatura – generale ----------------
    S(ZSM, "Zona di smerigliatura", "1.5.13", "Interno cella e locale di installazione", NORM, ["7.1"], (3, 5, 3, 3),
      [("PROG", "Lavorazione in cella chiusa in depressione.", None),
       ("PROT", "Bocchette di aspirazione presso ogni punto di smerigliatura, con portata indicata.", "EN ISO 14123-1"),
       ("PROT", "Consenso alla marcia dall'impianto di aspirazione (se fornito o collegato).", None),
       ("INFO", "Il manuale indica portata e depressione richieste all'impianto di aspirazione del cliente.", None)],
      "Non lavorare senza aspirazione attiva; impianto di aspirazione a cura del cliente secondo i dati del manuale.",
      (3, 5, 1, 1), B=("EN ISO 14123-1",), C=("EN ISO 16089",),
      nota="Decidere se il consenso dall'aspirazione è di serie."),
    S(ZSM, "Zona di smerigliatura", "1.5.6", "Interno cella, condotti di aspirazione", NORM, ["3.2"], (3, 4, 3, 3),
      [("PROG", "Materiali della cella non combustibili; nessun accumulo di polveri su superfici orizzontali interne.", "EN ISO 19353"),
       ("PROT", "Parascintille o separatore prima dei filtri dell'aspirazione.", None),
       ("INFO", "Il manuale indica pulizie periodiche e mezzi di estinzione adatti.", None)],
      "Pulire regolarmente cella e condotti; tenere estintori adeguati vicino all'impianto.", (3, 4, 1, 1), B=("EN ISO 19353",)),
    S(ZSM, "Zona di smerigliatura", "1.5.7", "Condotti e filtri di aspirazione", NORM, ["7.3"], (4, 3, 2, 3),
      [("PROG", "Valutazione della polvere prodotta (metallo, abrasivo) e della possibile atmosfera esplosiva.", "EN 1127-1"),
       ("INFO", "Il manuale indica i dati della polvere e le prescrizioni per l'impianto di aspirazione.", None)],
      "Impianto di aspirazione progettato dal cliente tenendo conto del rischio di esplosione delle polveri.", (4, 2, 1, 1),
      B=("EN 1127-1",), nota="Punto aperto: classificazione delle polveri da ottone e abrasivo."),
    S(ZSM, "Zona di smerigliatura", "1.6.5", "Interno cella e tramogge di raccolta", "Pulizia.", ["7.1", "1.12"], (3, 3, 3, 3),
      [("PROG", "Superfici interne lisce, inclinate verso i punti di raccolta.", None),
       ("PROT", "Pulizia interna solo a macchina ferma con energie isolate.", "EN ISO 14118"),
       ("INFO", "Il manuale indica frequenza della pulizia e DPI (maschera FFP3).", None)],
      "Per la pulizia interna usare maschera FFP3 e aspiratore, non aria compressa.", (3, 3, 1, 1), B=("EN ISO 14118",)),
    S(ZSM, "Zona di smerigliatura", "1.5.2", "Nastri abrasivi e condotti", NORM, ["2.3", "3.2"], (2, 4, 2, 3),
      [("PROG", "Parti metalliche, carter e condotti collegati a terra.", "EN 60204-1")],
      "", (2, 4, 1, 1), B=("EN 60204-1",)),

    # ---------------- Stazione di carico a doppio pallet ----------------
    S(PAL, "Zona di carico", "1.3.7", "Pallet in movimento tra carico e lavoro", NORM, ["1.1", "1.2"], (3, 5, 3, 3),
      [("PROT", "Zona di carico separata dalla zona di lavoro da riparo fisso; apertura di passaggio pallet solo per il pallet.", "EN ISO 14120"),
       ("PROT", "Scambio pallet solo con zona di carico libera, sorvegliata da barriera.", "EN ISO 13855"),
       ("PROG", "Spazi minimi tra pallet in movimento e struttura.", "EN ISO 13854")],
      "", (3, 5, 1, 1), B=("EN ISO 14120", "EN ISO 13855", "EN ISO 13854")),
    S(PAL, "Zona di carico", "1.4.3", "Accesso alla stazione di carico", NORM, ["1.1"], (3, 5, 3, 3),
      [("PROT", "Barriera fotoelettrica o scanner con PL adeguato; ripristino manuale dall'esterno.", "EN IEC 61496-1")],
      "", (3, 5, 1, 1), B=("EN IEC 61496-1", "EN ISO 13849-1")),
    S(PAL, "Zona di carico", "1.1.6", "Postazione di carico pallet", NORM, ["8.1", "8.2"], (2, 5, 3, 3),
      [("PROG", "Altezza del pallet ergonomica; posizioni dei pezzi raggiungibili senza sporgersi.", "EN 1005-2")],
      "", (2, 5, 1, 1), B=("EN 1005-2",)),
    S(PAL, "Zona di carico", "1.3.3", "Pezzi sul pallet durante lo scambio", NORM, ["1.10"], (2, 5, 2, 3),
      [("PROG", "Supporti dei pezzi con riferimenti che impediscono la caduta durante lo scambio.", None),
       ("PROT", "Controllo presenza pezzo prima dello scambio.", None)],
      "", (2, 5, 1, 1)),

    # ---------------- Gruppo di smerigliatura ----------------
    S(GSM, "Zona di smerigliatura", "1.3.8.2", "Area di lavoro del robot", "Normale; regolazione / attrezzamento; programmazione.",
      ["1.6", "1.1"], (4, 4, 3, 3),
      [("PROT", "Robot all'interno della cella chiusa; area di lavoro limitata con limiti software sicuri.", "EN ISO 10218-2"),
       ("PROT", "Accesso alla cella interbloccato; in programmazione velocità ridotta e dispositivo di abilitazione.", "EN ISO 10218-1")],
      "Programmazione solo da personale formato sul robot.", (3, 3, 1, 1), B=("EN ISO 14120",), C=("EN ISO 10218-1", "EN ISO 10218-2")),
    S(GSM, "Zona di smerigliatura", "1.3.8.1", "Pulegge, cinghie e motori delle smerigliatrici", "Manutenzione.", ["1.4", "1.5"], (3, 3, 3, 3),
      [("PROT", "Trasmissioni chiuse da ripari fissi.", "EN ISO 14120")],
      "", (3, 3, 1, 1), B=("EN ISO 14120",)),
    S(GSM, "Zona di smerigliatura", "1.3.8.2", "Nastro abrasivo e rulli di contatto", "Manutenzione; regolazione / attrezzamento.", ["1.7", "1.4"], (3, 4, 3, 3),
      [("PROT", "Carter sul nastro lasciando scoperta solo la zona di contatto con il pezzo.", "EN ISO 14120"),
       ("PROT", "Cambio nastro e regolazioni a nastro fermo e motore isolato.", "EN ISO 14118"),
       ("INFO", "Il manuale descrive la procedura di cambio nastro.", None)],
      "Cambio nastro solo a macchina ferma e isolata.", (3, 3, 1, 1), B=("EN ISO 14120", "EN ISO 14118"), C=("EN ISO 16089",)),
    S(GSM, "Zona di smerigliatura", "1.3.2", "Nastro abrasivo", NORM, ["1.9"], (3, 4, 3, 3),
      [("PROG", "Velocità del nastro non superiore a quella ammessa dal produttore dei nastri.", "EN 13743"),
       ("PROT", "Carter del nastro che trattiene il nastro in caso di rottura; sensore di rottura/sbandamento nastro.", None),
       ("INFO", "Il manuale indica i nastri ammessi (dimensioni, velocità massima).", None)],
      "Usare solo nastri con velocità massima ammessa non inferiore a quella indicata.", (3, 2, 1, 1), B=("EN 13743",)),
    S(GSM, "Zona di smerigliatura", "1.3.9", "Assi del robot", "Manutenzione; sblocco anomalie.", ["1.12", "1.10"], (4, 3, 2, 3),
      [("PROG", "Freni sugli assi del robot; mantenimento della posizione senza energia.", "EN ISO 10218-1"),
       ("INFO", "Il manuale indica come liberare una persona bloccata dal robot (sblocco freni).", None)],
      "", (4, 2, 1, 1), C=("EN ISO 10218-1",)),
    S(GSM, "Zona di smerigliatura", "1.3.6", "Pezzo nella pinza del robot", NORM, ["1.9"], (3, 4, 3, 3),
      [("PROG", "Programmi per articolo con parametri bloccati; scelta dell'articolo verificata dal sistema.", None),
       ("PROT", "Controllo presenza e posizione del pezzo nella pinza prima della smerigliatura.", None)],
      "", (3, 4, 1, 1)),
    S(GSM, "Zona di smerigliatura", "1.5.5", "Rulli di contatto e pezzi appena smerigliati", "Manutenzione; sblocco anomalie.", ["3.1"], (2, 3, 3, 3),
      [("INFO", "Avvertenza sul pericolo di superfici calde presso le smerigliatrici e nel manuale.", "EN ISO 7010")],
      "Attendere il raffreddamento o usare guanti prima di toccare rulli e pezzi.", (2, 3, 2, 3), B=("EN ISO 13732-1", "EN ISO 7010")),
    S(GSM, "Zona di smerigliatura", "1.6.4", "Cambio nastro e regolazioni", "Manutenzione; regolazione / attrezzamento.", ["1.12"], (3, 4, 3, 3),
      [("PROG", "Sistema di tensionamento e cambio nastro rapido, senza attrezzi speciali.", None),
       ("PROT", "Sezionamento locale lucchettabile della singola smerigliatrice.", "EN ISO 14118")],
      "", (3, 3, 1, 1), B=("EN ISO 14118",)),

    # ---------------- Trasportatore di scarico ----------------
    S(TRA, "Zona di scarico", "1.3.8.1", "Motoriduttore e trasmissioni del nastro", "Manutenzione.", ["1.4", "1.5"], (3, 3, 3, 3),
      [("PROT", "Trasmissioni chiuse da ripari fissi.", "EN ISO 14120")],
      "", (3, 3, 1, 1), B=("EN ISO 14120",)),
    S(TRA, "Zona di scarico", "1.3.7", "Punti di ingresso tra tappeto e rulli", NORM, ["1.4"], (3, 5, 2, 3),
      [("PROT", "Ripari sui punti di ingresso dei rulli; distanze di sicurezza rispettate.", "EN ISO 13857"),
       ("PROG", "Velocità del nastro bassa.", None)],
      "", (3, 5, 1, 1), B=("EN ISO 13857", "EN ISO 14120")),
    S(TRA, "Zona di scarico", "1.2.4.3", "Lungo il trasportatore", NORM, ["1.4"], (3, 5, 2, 3),
      [("PROG", "Pulsante di emergenza presso il punto di prelievo dei pezzi.", "EN ISO 13850")],
      "", (3, 5, 1, 1), B=("EN ISO 13850",)),
    S(TRA, "Zona di scarico", "1.5.5", "Pezzi sul nastro di uscita", NORM, ["3.1"], (2, 5, 3, 3),
      [("PROG", "Lunghezza del nastro tale da permettere il raffreddamento dei pezzi.", None),
       ("INFO", "Il manuale indica i guanti da usare per il prelievo.", None)],
      "Usare guanti per il prelievo dei pezzi.", (2, 5, 1, 3), B=("EN ISO 13732-1",)),

    # ---------------- Zona pulitura – generale ----------------
    S(ZPU, "Zona di pulitura", "1.5.13", "Interno cella e locale di installazione", NORM, ["7.1", "7.4"], (3, 5, 3, 3),
      [("PROG", "Lavorazione in cella chiusa in depressione.", None),
       ("PROT", "Aspirazione presso ogni unità di lucidatura, dimensionata per fibre e residui di pasta.", "EN ISO 14123-1"),
       ("INFO", "Il manuale indica portata e depressione richieste all'aspirazione del cliente.", None)],
      "Non lavorare senza aspirazione attiva.", (3, 5, 1, 1), B=("EN ISO 14123-1",)),
    S(ZPU, "Zona di pulitura", "1.5.6", "Interno cella, condotti e filtri", NORM, ["3.2"], (3, 4, 4, 3),
      [("PROG", "Residui di cotone e pasta considerati combustibili: superfici interne lisce, nessun punto di accumulo.", "EN ISO 19353"),
       ("PROT", "Valutare rivelazione e spegnimento automatico nella cella o nei condotti.", None),
       ("INFO", "Il manuale indica frequenza di pulizia di cella e condotti e mezzi di estinzione adatti.", None)],
      "Pulire cella e condotti alla frequenza indicata; non lasciare stracci o residui nella cella.", (3, 4, 2, 1), B=("EN ISO 19353",),
      nota="Rischio incendio da considerare con attenzione nella zona di pulitura."),
    S(ZPU, "Zona di pulitura", "1.5.7", "Condotti e filtri di aspirazione", NORM, ["7.3"], (4, 3, 2, 3),
      [("PROG", "Valutazione delle polveri (fibre tessili, pasta, metallo) e della possibile atmosfera esplosiva.", "EN 1127-1"),
       ("INFO", "Il manuale riporta le prescrizioni per l'impianto di aspirazione del cliente.", None)],
      "", (4, 2, 1, 1), B=("EN 1127-1",), nota="Punto aperto: classificazione delle polveri di lucidatura."),
    S(ZPU, "Zona di pulitura", "1.6.5", "Interno cella", "Pulizia.", ["7.1", "7.2"], (2, 4, 3, 3),
      [("PROT", "Pulizia solo a macchina ferma con energie isolate.", "EN ISO 14118"),
       ("INFO", "Il manuale indica frequenza della pulizia e DPI (guanti, maschera).", None)],
      "Usare guanti e maschera per la pulizia interna.", (2, 4, 1, 1), B=("EN ISO 14118",)),

    # ---------------- Unità di lucidatura CNC ----------------
    S(LUC, "Zona di pulitura", "1.3.8.2", "Dischi o spazzole in rotazione", "Normale; regolazione / attrezzamento.", ["1.5", "1.4", "1.7"], (3, 4, 3, 3),
      [("PROT", "Unità all'interno della cella chiusa; carter sul disco lasciando scoperta solo la zona di lavoro.", "EN ISO 14120"),
       ("PROT", "Porte interbloccate con arresto del disco prima dell'apertura (bloccaggio fino a fermo).", "EN ISO 14119")],
      "", (3, 3, 1, 1), B=("EN ISO 14120", "EN ISO 14119")),
    S(LUC, "Zona di pulitura", "1.3.8.1", "Motori e trasmissioni dell'unità", "Manutenzione.", ["1.4", "1.5"], (3, 3, 3, 3),
      [("PROT", "Trasmissioni chiuse da ripari fissi.", "EN ISO 14120")],
      "", (3, 3, 1, 1), B=("EN ISO 14120",)),
    S(LUC, "Zona di pulitura", "1.3.2", "Dischi e spazzole", NORM, ["1.9"], (3, 4, 3, 3),
      [("PROG", "Velocità periferica non superiore a quella ammessa per dischi e spazzole.", None),
       ("PROT", "Carter che trattiene frammenti di disco o spazzola.", "EN ISO 14120"),
       ("INFO", "Il manuale indica dischi e spazzole ammessi e la velocità massima.", None)],
      "Usare solo dischi e spazzole con velocità ammessa non inferiore a quella indicata.", (3, 2, 1, 1), B=("EN ISO 14120",)),
    S(LUC, "Zona di pulitura", "1.3.9", "Assi CNC dell'unità", "Manutenzione; sblocco anomalie.", ["1.12", "1.1"], (3, 3, 3, 3),
      [("PROG", "Assi verticali con freno o motore autofrenante; trascinamenti irreversibili.", None),
       ("PROT", "Arresto sicuro degli assi con porte aperte.", "EN ISO 13849-1")],
      "", (3, 3, 1, 1), B=("EN ISO 13849-1",)),
    S(LUC, "Zona di pulitura", "1.6.4", "Sostituzione di dischi e spazzole", "Manutenzione; regolazione / attrezzamento.", ["1.12", "1.5"], (3, 4, 3, 3),
      [("PROG", "Sostituzione rapida senza attrezzi speciali, da posizione accessibile.", None),
       ("PROT", "Sezionamento locale lucchettabile dell'unità.", "EN ISO 14118")],
      "Sostituzioni solo a unità ferma e isolata.", (3, 3, 1, 1), B=("EN ISO 14118",)),
    S(LUC, "Zona di pulitura", "1.5.5", "Dischi e pezzi dopo la lucidatura", "Manutenzione; sblocco anomalie.", ["3.1"], (2, 3, 3, 3),
      [("INFO", "Avvertenza superfici calde presso l'unità e nel manuale.", "EN ISO 7010")],
      "Attendere il raffreddamento o usare guanti.", (2, 3, 2, 3), B=("EN ISO 13732-1", "EN ISO 7010")),

    # ---------------- Equipaggiamento elettrico ----------------
    S(ELE, "Quadro elettrico", "1.5.1", "Quadro elettrico e componenti sotto tensione", "Manutenzione.", ["2.1"], (4, 3, 3, 3),
      [("PROG", "Parti attive protette con grado di protezione adeguato (almeno IP2X / IPXXB).", "EN 60204-1"),
       ("PROT", "Porta del quadro apribile solo con attrezzo o con sezionatore aperto.", None),
       ("INFO", "Segnale di pericolo elettrico sul quadro; interventi solo da personale qualificato (PES/PAV).", "EN ISO 7010")],
      "Interventi elettrici solo da personale qualificato.", (4, 2, 1, 1), B=("EN 60204-1", "EN IEC 61439-1")),
    S(ELE, "Impianto", "1.5.1", "Masse metalliche dell'impianto", TUTTE, ["2.2"], (4, 3, 2, 3),
      [("PROG", "Circuito di protezione equipotenziale; protezione contro i contatti indiretti con interruzione automatica.", "EN 60204-1"),
       ("PROT", "Verifiche di continuità e isolamento al collaudo.", None),
       ("INFO", "Il manuale indica le caratteristiche dell'alimentazione e della protezione a monte richiesta.", None)],
      "", (4, 2, 1, 1), B=("EN 60204-1",)),
    S(ELE, "Quadro elettrico", "1.6.3", "Sezionatore generale", "Manutenzione; pulizia.", ["1.12", "2.1"], (4, 3, 3, 3),
      [("PROG", "Sezionatore generale lucchettabile in posizione aperto, facilmente raggiungibile.", "EN 60204-1"),
       ("INFO", "Il manuale indica le parti che restano in tensione dopo il sezionamento.", None)],
      "Bloccare il sezionatore con lucchetto personale prima di ogni intervento.", (4, 2, 1, 1), B=("EN 60204-1", "EN ISO 14118")),
    S(ELE, "Quadro elettrico", "1.5.6", "Quadro elettrico e cavi", TUTTE, ["2.4", "3.2"], (3, 2, 2, 3),
      [("PROG", "Protezioni contro sovraccarico e cortocircuito; cavi dimensionati e non propaganti la fiamma.", "EN 60204-1")],
      "", (3, 2, 1, 1), B=("EN 60204-1",)),

    # ---------------- Equipaggiamento pneumatico ----------------
    S(PNE, "Impianto pneumatico", "1.5.3", "Tubazioni e attuatori pneumatici", "Normale; manutenzione.", ["1.11"], (2, 4, 2, 3),
      [("PROG", "Tubi e raccordi adatti alla pressione massima; tubi fissati per evitare colpi di frusta.", "EN ISO 4414"),
       ("PROG", "Regolatore e valvola di sicurezza sul gruppo trattamento aria.", None)],
      "", (2, 4, 1, 1), B=("EN ISO 4414",)),
    S(PNE, "Impianto pneumatico", "1.6.3", "Gruppo trattamento aria", "Manutenzione.", ["1.12", "1.11"], (3, 3, 3, 3),
      [("PROG", "Valvola di sezionamento lucchettabile con scarico della pressione residua.", "EN ISO 4414"),
       ("INFO", "Il manuale indica i circuiti che restano in pressione (accumuli, ritegni) e come scaricarli.", None)],
      "Sezionare e scaricare l'aria prima di intervenire sugli attuatori.", (3, 3, 1, 1), B=("EN ISO 4414", "EN ISO 14118")),
    S(PNE, "Impianto pneumatico", "1.2.6", "Attuatori pneumatici", TUTTE, ["1.12", "1.10"], (3, 2, 3, 3),
      [("PROG", "Al calo di pressione gli attuatori restano in posizione sicura; pressostato con arresto dell'impianto.", "EN ISO 4414")],
      "", (3, 2, 1, 1), B=("EN ISO 4414",)),
    S(PNE, "Impianto pneumatico", "1.5.8", "Scarichi delle valvole", NORM, ["4.1"], (1, 5, 3, 3),
      [("PROG", "Silenziatori su tutti gli scarichi.", "EN ISO 4414")],
      "", (1, 5, 2, 1), B=("EN ISO 4414",)),

    # ---------------- Impianto pasta abrasiva ----------------
    S(PAS, "Zona di pulitura", "1.5.13", "Serbatoio, ugelli e zona di spruzzatura", "Normale; manutenzione.", ["7.2", "7.4"], (2, 4, 3, 3),
      [("PROG", "Spruzzatura all'interno della cella aspirata.", None),
       ("INFO", "Il manuale chiede di seguire la scheda di sicurezza della pasta e indica i DPI per il rabbocco.", None)],
      "Seguire la scheda di sicurezza della pasta; usare guanti per rabbocco e pulizia.", (2, 4, 1, 3)),
    S(PAS, "Zona di pulitura", "1.5.3", "Pompa e tubazioni della pasta", "Normale; manutenzione.", ["1.11", "7.2"], (2, 3, 2, 3),
      [("PROG", "Tubazioni adatte alla pressione della pompa; valvola di sicurezza.", None),
       ("PROT", "Scarico della pressione prima di aprire tubi o ugelli.", None)],
      "Scaricare la pressione prima di intervenire sul circuito della pasta.", (2, 3, 1, 1)),
    S(PAS, "Zona di pulitura", "1.6.1", "Pulizia di ugelli e filtri", "Manutenzione; pulizia.", ["7.2"], (2, 4, 3, 3),
      [("PROG", "Ugelli e filtri raggiungibili dall'esterno della cella.", None),
       ("INFO", "Il manuale descrive la pulizia e i prodotti da usare.", None)],
      "", (2, 4, 1, 3)),
    S(PAS, "Zona di pulitura", "1.5.15", "Pavimento presso il serbatoio", "Normale; manutenzione.", ["9.1"], (2, 4, 3, 3),
      [("PROG", "Vasca di raccolta sotto serbatoio e pompa.", None)],
      "", (2, 4, 1, 1)),

    # ---------------- Informazioni, marcatura e istruzioni ----------------
    S(INF, "Impianto", "1.7.1.1", "Pannello operatore", TUTTE, ["8.4"], (2, 5, 2, 3),
      [("PROG", "Messaggi di allarme e stato in lingua del paese di utilizzo, comprensibili senza ambiguità.", "EN 61310-1")],
      "", (2, 5, 1, 1), B=("EN 61310-1",)),
    S(INF, "Impianto", "1.7.1.2", "Segnalazione di stato dell'impianto", TUTTE, ["4.2", "8.4"], (2, 5, 2, 3),
      [("PROG", "Colonna luminosa con colori secondo norma; segnale acustico per allarmi e avvio.", "EN 61310-1")],
      "", (2, 5, 1, 1), B=("EN 61310-1", "EN 60204-1")),
    S(INF, "Impianto", "1.7.2", "Punti con rischi residui", TUTTE, [], None,
      [("INFO", "Segnali di avvertimento e obbligo (ISO 7010) presso porte, quadro, superfici calde, zona di carico.", "EN ISO 7010"),
       ("INFO", "Il manuale riassume tutti i rischi residui in un capitolo dedicato.", None)],
      "Elenco dei rischi residui generato dalla valutazione.", None, B=("EN ISO 7010",), nota=DESCRITTIVA),
    S(INF, "Impianto", "1.7.3", "Targa dell'impianto", TUTTE, [], None,
      [("INFO", "Targa con ragione sociale e indirizzo del fabbricante, designazione, serie/tipo, matricola, anno, marcatura CE.", None)],
      "", None, nota=DESCRITTIVA),
    S(INF, "Impianto", "1.7.4.1", "Manuale di istruzioni", TUTTE, [], None,
      [("INFO", "Istruzioni originali in italiano e traduzione nella lingua del paese di utilizzo.", "EN ISO 20607"),
       ("INFO", "Formato digitale con copia cartacea gratuita se richiesta all'acquisto; sicurezza essenziale anche su carta.", None)],
      "", None, B=("EN ISO 20607",), nota=DESCRITTIVA),
    S(INF, "Impianto", "1.7.4.2", "Manuale di istruzioni", TUTTE, [], None,
      [("INFO", "Contenuto del manuale verificato con l'elenco del RESS: uso previsto, installazione, uso, manutenzione, rumore, rischi residui, DPI.", "EN ISO 20607")],
      "", None, B=("EN ISO 20607",), nota=DESCRITTIVA),
    S(INF, "Impianto", "1.7.4.3", "Cataloghi e materiale commerciale", TUTTE, [], None,
      [("INFO", "Il materiale commerciale non contraddice le istruzioni; riporta i valori di rumore come nel manuale.", None)],
      "", None, nota=DESCRITTIVA),
]

# Criterio per la Fr finale. "reale" (scelto da Cosmap il 5/10/2026): la Fr finale resta la frequenza reale
# con cui la persona è presso la zona; le protezioni riducono Pr e Av. "ridotta": come nella prima
# estrazione, dopo ripari e interblocchi Fr = 2, salvo i pericoli a cui si resta esposti anche con le protezioni.
CRITERIO_FR = "reale"
PERICOLI_ESPOSIZIONE_CONTINUA = ("3.1", "4.", "7.1", "7.2", "7.4", "8.", "9.1")
MODULI_CARICO_MANUALE = (TAV, PAL)


def fr_finale_ridotta(scheda):
    if not scheda["sf"] or not any(tipo == "PROT" for tipo, _, _ in scheda["mis"]):
        return False
    if scheda["modulo"] in MODULI_CARICO_MANUALE and scheda["ress"] in ("1.3.7", "1.3.8.2", "1.4.3"):
        return False
    return not any(p.startswith(PERICOLI_ESPOSIZIONE_CONTINUA) for p in scheda["per"])


for scheda in SCHEDE:
    if CRITERIO_FR == "ridotta" and fr_finale_ridotta(scheda):
        se, _, pr, av = scheda["sf"]
        scheda["sf"] = (se, 2, pr, av)

# Rischio residuo per le schede che non si chiudono in verde: (modulo, RESS) -> testo
RESIDUI = {
    (CMD, "1.2.1"): "Rischio residuo legato a guasti non rilevati: non modificare cablaggi e programmi di sicurezza; eseguire le verifiche periodiche delle funzioni di sicurezza indicate nel manuale.",
    (CMD, "1.2.2"): "Usare i comandi solo come descritto nel manuale; formazione degli operatori sul pannello.",
    (CMD, "1.2.3"): "Prima dell'avvio verificare che nessuno sia nelle zone pericolose.",
    (CMD, "1.2.4.1"): "L'arresto normale non è un comando di sicurezza: per entrare usare la procedura di accesso.",
    (CMD, "1.2.4.2"): "Durante gli arresti operativi la macchina può ripartire: non entrare senza aprire le porte interbloccate.",
    (CMD, "1.2.4.3"): "L'arresto di emergenza non sostituisce il sezionamento per manutenzione; verificarne il funzionamento periodicamente.",
    (CMD, "1.2.6"): "Dopo una mancanza di energia verificare lo stato dell'impianto e dei pezzi in pinza prima del riavvio.",
    (CAB, "1.3.7"): "Non eludere ripari e interblocchi; segnalare subito ripari danneggiati.",
    (CAB, "1.4.2.1"): "Rimontare sempre i pannelli fissi dopo la manutenzione, prima di riavviare.",
    (CAB, "1.4.2.2"): "Non eludere i dispositivi di interblocco; verificarne periodicamente il funzionamento.",
    (CAB, "1.4.3"): "Verificare periodicamente il funzionamento dei dispositivi di protezione come indicato nel manuale.",
    (CAB, "1.3.3"): "Sostituire i pannelli trasparenti graffiati o danneggiati.",
    (TAV, "1.3.8.2"): "Non avvicinare le mani alla tavola durante la rotazione; formazione degli operatori al carico.",
    (TAV, "1.4.3"): "Verificare ogni giorno il funzionamento del dispositivo di protezione della zona di carico.",
    (PAL, "1.3.7"): "Non intervenire sul pallet durante lo scambio; formazione degli operatori al carico.",
    (PAL, "1.4.3"): "Verificare ogni giorno il funzionamento della barriera della zona di carico.",
    (GSM, "1.3.8.1"): "Rimontare i ripari delle trasmissioni dopo la manutenzione.",
    (GSM, "1.3.9"): "In caso di persona bloccata dal robot seguire la procedura di sblocco freni del manuale.",
    (GSM, "1.3.6"): "Usare solo i programmi associati all'articolo da lavorare.",
    (GSM, "1.6.4"): "Isolare la smerigliatrice con il proprio lucchetto prima del cambio nastro.",
    (TRA, "1.3.8.1"): "Rimontare i ripari delle trasmissioni dopo la manutenzione.",
    (TRA, "1.3.7"): "Non togliere pezzi incastrati con il nastro in moto.",
    (TRA, "1.2.4.3"): "Verificare periodicamente il pulsante di emergenza del trasportatore.",
    (LUC, "1.3.8.2"): "Non eludere gli interblocchi delle porte; attendere l'arresto dei dischi.",
    (LUC, "1.3.8.1"): "Rimontare i ripari delle trasmissioni dopo la manutenzione.",
    (LUC, "1.3.9"): "Prima di lavorare sotto un asse verticale verificarne il blocco meccanico.",
    (ELE, "1.5.1"): "Fare verificare periodicamente l'impianto di terra e le protezioni a monte.",
    (PAS, "1.6.1"): "Usare guanti e occhiali per la pulizia di ugelli e filtri.",
    (ZPU, "1.5.7"): "Impianto di aspirazione progettato dal cliente tenendo conto del rischio di esplosione delle polveri.",
}
for scheda in SCHEDE:
    testo_residuo = RESIDUI.get((scheda["modulo"], scheda["ress"]))
    if testo_residuo and not scheda["istr"]:
        scheda["istr"] = testo_residuo

# ---------------------------------------------------------------------------
# Soggetti esposti (RESS 1.1.1 c e d): nomi come le figure standard del programma
# ---------------------------------------------------------------------------

CONDUZIONE, ATTREZZAGGIO, MANUT_MECC, MANUT_ELETT, PROGRAMMATORE, PULIZIE, INSTALLATORE, TERZI = (
    "Operatore di conduzione",
    "Operatore di attrezzaggio",
    "Manutentore meccanico",
    "Manutentore elettrico",
    "Programmatore",
    "Addetto alle pulizie",
    "Installatore / collaudatore",
    "Terzi di passaggio",
)
# Pericoli che durante il funzionamento raggiungono anche chi passa vicino alla macchina
PERICOLI_VERSO_ESTERNO = ("3.2", "4.1", "4.2", "7.1", "7.3", "7.4", "9.1")


def soggetti_scheda(scheda):
    """Soggetti esposti proposti in base a condizioni operative, modulo e pericoli."""
    if not scheda["per"]:
        return []
    condizioni = scheda["cond"].lower()
    elettrico = scheda["modulo"] == ELE or any(p.startswith("2.") for p in scheda["per"])
    tutte = "tutte" in condizioni
    soggetti = []
    if tutte or "normale" in condizioni or "sblocco" in condizioni:
        soggetti.append(CONDUZIONE)
    if "regolazione" in condizioni:
        soggetti.append(ATTREZZAGGIO)
    if "programmazione" in condizioni:
        soggetti.append(PROGRAMMATORE)
    if tutte or "manutenzione" in condizioni or "sblocco" in condizioni:
        soggetti.append(MANUT_ELETT if elettrico else MANUT_MECC)
    if "pulizia" in condizioni:
        soggetti.append(PULIZIE)
    if any(fase in condizioni for fase in ("installazione", "trasporto", "smantellamento")):
        soggetti.append(INSTALLATORE)
    in_funzione = tutte or "normale" in condizioni
    verso_esterno = any(p in PERICOLI_VERSO_ESTERNO for p in scheda["per"])
    if in_funzione and (verso_esterno or (scheda["modulo"] == CAB and "1.9" in scheda["per"])):
        soggetti.append(TERZI)
    return list(dict.fromkeys(soggetti))


for scheda in SCHEDE:
    scheda["soggetti"] = soggetti_scheda(scheda)

# Codici: sigla del modulo e numero progressivo nel modulo, nell'ordine delle schede
_contatori = {}
for scheda in SCHEDE:
    _contatori[scheda["modulo"]] = _contatori.get(scheda["modulo"], 0) + 1
    scheda["codice"] = f"{SIGLE[scheda['modulo']]}-{_contatori[scheda['modulo']]:02d}"

# ---------------------------------------------------------------------------
# Scrittura del file
# ---------------------------------------------------------------------------

GRASSETTO = Font(bold=True)
INTESTAZIONE = PatternFill("solid", fgColor="DDE4EE")


def intestazione(ws, colonne, larghezze=None):
    ws.append(colonne)
    for cella in ws[1]:
        cella.font = GRASSETTO
        cella.fill = INTESTAZIONE
        cella.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    for i, larghezza in enumerate(larghezze or [], start=1):
        ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = larghezza


def testo_misure(misure):
    righe = []
    for tipo, testo, norma in misure:
        righe.append(f"{tipo}: {testo}" + (f" {{{norma}}}" if norma else ""))
    return "\n".join(righe)


def testo_norme(scheda):
    parti = []
    for gruppo in ("A", "B", "C"):
        if scheda[gruppo]:
            parti.append(f"Norme {gruppo}: " + ", ".join(scheda[gruppo]))
    return " ".join(parti)


def genera():
    wb = openpyxl.Workbook()

    ws = wb.active
    ws.title = "Leggimi"
    for riga in [
        "Libreria analisi dei rischi Cosmap – nuova libreria costruita da zero",
        "",
        "Costruita senza usare la prima estrazione dalla valutazione 200741V.",
        "Fonti: Regolamento (UE) 2023/1230 Allegato III; EN ISO 12100 (tipi di pericolo, con parole nostre);",
        "metodo ibrido ISO/TR 14121-2 per la stima; norme armonizzate di uso comune per celle di smerigliatura e lucidatura.",
        "",
        "Le stime Se/Fr/Pr/Av sono PROPOSTE da validare da parte del tecnico Cosmap prima dell'uso.",
        "Criterio Fr finale: Fr reale, cioè la frequenza con cui la persona è presso la zona anche dopo le protezioni;",
        "le misure di protezione riducono la probabilità (Pr) e la possibilità di evitare il danno (Av).",
        "Le misure sono nel foglio Misure, una per riga, con il tipo (PROG progettazione, PROT protezione,",
        "INFO informazioni) e la norma di riferimento. La colonna misure del foglio Libreria è solo una sintesi.",
        "Codici delle schede: sigla del modulo e numero nel modulo (es. GEN-01, TAV-03); sigle nel foglio Moduli.",
        "Codici dei pericoli a due cifre (es. 1.01) per non confondersi con quelli della prima estrazione.",
        "Soggetti esposti proposti in base a condizioni operative e pericoli (ultima colonna del foglio Libreria):",
        "operatori secondo il RESS 1.1.1 d) e persone esposte secondo il RESS 1.1.1 c).",
        "Edizioni e stato di armonizzazione delle norme vanno verificati sulla GUUE.",
        "",
        "Requisiti senza scheda (di regola non applicabili, da dichiarare nell'applicabilità):",
        "1.1.8 Sedile; 1.4.2.3 Ripari regolabili; 1.5.9 Vibrazioni; 1.5.10 Radiazioni; 1.5.11 Radiazioni esterne;",
        "1.5.12 Radiazioni laser; 1.5.16 Fulmine.",
        "",
        "Fogli: Libreria (schede), Misure, Moduli, RESS-Regolamento, Norme, Pericoli, Metodo, Punti aperti.",
        "Il file si rigenera con: python dati/genera_libreria_nuova.py",
    ]:
        ws.append([riga])
    ws.column_dimensions["A"].width = 120

    # Libreria
    ws = wb.create_sheet("Libreria")
    intestazione(ws, [
        "ID", "RESS", "Titolo requisito", "Scheda originale", "Zona impianto", "Modulo", "Condizione di attivazione",
        "Zona pericolosa", "Condizioni operative", "Pericoli", "Se iniz.", "Fr iniz.", "Pr iniz.", "Av iniz.",
        "Cl iniz.", "Esito iniziale", "Misure di protezione (sintesi: dettaglio nel foglio Misure)", "Indicazioni per le istruzioni / rischio residuo",
        "Se fin.", "Fr fin.", "Pr fin.", "Av fin.", "Cl fin.", "Esito finale", "Norme citate", "Note di revisione",
        "Soggetti esposti",
    ], [9, 8, 30, 8, 16, 26, 20, 30, 22, 34, 6, 6, 6, 6, 6, 10, 70, 45, 6, 6, 6, 6, 6, 10, 40, 35, 40])
    titoli = {r[2]: r[1] for r in RESS}
    condizioni_modulo = {nome: condizione for nome, condizione, _ in MODULI}
    for n, s in enumerate(SCHEDE, start=1):
        cl_i, es_i = esito(s["si"])
        cl_f, es_f = esito(s["sf"])
        note = s["nota"]
        if s["si"]:
            note = (note + " " if note else "") + "Stima proposta, da validare."
        ws.append([
            s["codice"], s["ress"], titoli[s["ress"]], "", s["zona"], s["modulo"], condizioni_modulo[s["modulo"]],
            s["zp"], s["cond"], "\n".join(f"{codice_pericolo(c)} {PERICOLI[c]}" for c in s["per"]),
            *(s["si"] or (None,) * 4), cl_i, es_i,
            testo_misure(s["mis"]), s["istr"],
            *(s["sf"] or (None,) * 4), cl_f, es_f,
            testo_norme(s), note, "; ".join(s["soggetti"]),
        ])
    for riga in ws.iter_rows(min_row=2):
        for cella in riga:
            cella.alignment = Alignment(wrap_text=True, vertical="top")

    # Misure: una per riga, lette dall'importazione
    ws = wb.create_sheet("Misure")
    intestazione(ws, ["ID scheda", "Ordine", "Tipo", "Descrizione tipo", "Misura", "Norma"], [10, 7, 7, 34, 90, 18])
    descrizione_tipo = {
        "PROG": "Progettazione intrinsecamente sicura",
        "PROT": "Protezione e misure complementari",
        "INFO": "Informazioni per l'uso",
    }
    for n, s in enumerate(SCHEDE, start=1):
        for ordine, (tipo, testo, norma) in enumerate(s["mis"], start=1):
            ws.append([s["codice"], ordine, tipo, descrizione_tipo[tipo], testo, norma])
    for riga in ws.iter_rows(min_row=2):
        riga[4].alignment = Alignment(wrap_text=True, vertical="top")

    # Moduli
    ws = wb.create_sheet("Moduli")
    intestazione(ws, ["Modulo", "Schede in libreria", "Condizione di attivazione proposta",
                      "Schede con esito finale non verde", "Note", "Sigla"], [50, 10, 50, 12, 70, 8])
    for nome, condizione, descrizione in MODULI:
        schede = [s for s in SCHEDE if s["modulo"] == nome]
        non_verdi = sum(1 for s in schede if s["sf"] and esito(s["sf"])[1] != "OK")
        ws.append([nome, len(schede), condizione, non_verdi, descrizione, SIGLE[nome]])

    # RESS
    ws = wb.create_sheet("RESS-Regolamento")
    intestazione(ws, ["RESS All. I 2006/42/CE", "Titolo", "Schede nella nuova libreria", "Stato",
                      "Punto All. III Reg. (UE) 2023/1230", "Novità del Regolamento (sintesi da verificare sul testo ufficiale)",
                      "Azione per la libreria"], [12, 50, 10, 16, 12, 80, 50])
    for direttiva, titolo, regolamento, novita, azione in RESS:
        quante = sum(1 for s in SCHEDE if s["ress"] == regolamento)
        stato = "Trattato" if quante else "Di regola non applicabile"
        ws.append([direttiva, titolo, quante, stato, regolamento, novita, azione])

    # Norme
    ws = wb.create_sheet("Norme")
    intestazione(ws, ["Norma", "Edizione di riferimento", "Oggetto", "Edizione più recente nota", "Nota",
                      "Armonizzata", "Tipo"], [20, 16, 70, 18, 60, 12, 6])
    for riga in NORME:
        ws.append(list(riga) + ["No" if riga[0] in NON_ARMONIZZATE else "Sì", tipo_norma(riga[0])])

    # Pericoli
    ws = wb.create_sheet("Pericoli")
    intestazione(ws, ["Codice", "Pericolo", "Schede"], [8, 70, 8])
    for codice, descrizione in PERICOLI.items():
        ws.append([codice_pericolo(codice), descrizione, sum(1 for s in SCHEDE if codice in s["per"])])

    # Metodo
    ws = wb.create_sheet("Metodo")
    ws.append(["Metodo di stima del rischio: ibrido ISO/TR 14121-2 (gravità e classe Cl = Fr + Pr + Av)"])
    ws.append([])
    ws.append(["Matrice: esito in funzione di gravità (Se) e classe (Cl)"])
    ws.append([None, "Se"] + [f"Cl {lo}-{hi}" for lo, hi in FASCE])
    ws.append(["Limite inferiore classe", None] + [lo for lo, _ in FASCE])
    for se in (4, 3, 2, 1):
        ws.append([NOMI_SE[se], se] + MATRICE[se])
    ws.append([])
    for fattore, valori in SCALE.items():
        ws.append([fattore])
        for valore, descrizione in valori:
            ws.append([None, valore, descrizione])
    ws.append([])
    ws.append(["Nota: la cella Se 4 / Cl 3-4 (misure suggerite) va confrontata con la tabella dell'ISO/TR 14121-2."])
    ws.column_dimensions["A"].width = 45
    ws.column_dimensions["C"].width = 60

    # Punti aperti
    ws = wb.create_sheet("Punti aperti")
    intestazione(ws, ["N.", "Tema", "Situazione", "Decisione da prendere", "Decisione Cosmap"], [5, 30, 70, 70, 40])
    for n, (tema, situazione, decisione) in enumerate([
        ("Stime", "Tutte le stime sono proposte costruite da zero, senza la valutazione 200741V.",
         "Validare le stime con il tecnico, a partire dalle schede con Se 3 e 4."),
        ("Matrice Se 4 / Cl 3-4", "Impostata a 'misure suggerite' come esempio dell'ISO/TR 14121-2.",
         "Confermare sulla norma; con 'richieste' nessuna scheda con Se 4 potrebbe chiudersi in verde."),
        ("Esplosione da polveri", "Schede 1.5.7 in zona smerigliatura e pulitura con la sola valutazione da fare.",
         "Classificare le polveri (ottone, abrasivo, fibre) e definire le prescrizioni per l'aspirazione."),
        ("Aspirazione", "L'aspirazione è considerata a carico del cliente con dati nel manuale.",
         "Decidere se il consenso alla marcia dall'aspirazione è di serie."),
        ("Incendio in zona pulitura", "Residui di cotone e pasta sono combustibili; proposta valutazione spegnimento automatico.",
         "Decidere lo standard Cosmap (pulizie, rivelazione, spegnimento)."),
        ("Norma di prodotto", "EN ISO 16089 citata come riferimento per la smerigliatura.",
         "Verificare se il campo di applicazione copre le macchine Cosmap; se no, restano le norme A e B."),
        ("Corruzione e software (1.1.9, 1.2.1)", "Requisiti nuovi del Regolamento: misure proposte su password, rete, tracciamento.",
         "Definire con il fornitore PLC/robot le misure standard."),
        ("Requisiti non applicabili", "7 requisiti senza scheda (vedi Leggimi).",
         "Confermare che di regola sono non applicabili e la motivazione standard."),
    ], start=1):
        ws.append([n, tema, situazione, decisione, None])

    wb.save(USCITA)
    print(f"Creato {USCITA.name}: {len(SCHEDE)} schede, {len(RESS)} requisiti, {len(NORME)} norme, {len(MODULI)} moduli")


if __name__ == "__main__":
    genera()
