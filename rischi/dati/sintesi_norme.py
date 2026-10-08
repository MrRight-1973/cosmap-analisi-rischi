"""Sintesi di ogni norma della libreria: a cosa si riferisce e quando richiamarla nelle schede.

Testi scritti per l'app (non estratti dalle norme): orientano il tecnico, il riferimento resta il testo
ufficiale della norma nell'edizione citata. Caricati nel campo "nota" dalla migrazione 0028."""

SINTESI = {
    "EN ISO 12100": "Norma di tipo A: principi generali per la progettazione sicura. Definisce il processo di "
    "valutazione del rischio (limiti della macchina, identificazione dei pericoli, stima e ponderazione) e la "
    "riduzione del rischio in tre passi: progettazione intrinsecamente sicura, protezioni e misure complementari, "
    "informazioni per l'uso. Contiene l'elenco dei pericoli tipici (allegato B) usato nelle schede.",
    "ISO/TR 14121-2": "Rapporto tecnico di supporto alla EN ISO 12100: guida pratica alla valutazione del rischio "
    "con esempi di metodi di stima (matrici, grafi, punteggi). È la base del metodo ibrido usato nell'app "
    "(gravità Se e classe Cl = Fr + Pr + Av).",
    "EN ISO 13849-1": "Progettazione delle parti dei sistemi di comando legate alla sicurezza (SRP/CS) di qualsiasi "
    "tecnologia. Definisce il livello di prestazione richiesto PLr (grafo di rischio con S, F, P), le categorie "
    "di architettura, MTTFd, DCavg e guasti di causa comune per raggiungere il PL. Da richiamare per ogni funzione "
    "di sicurezza: interblocchi, arresti, barriere, consensi.",
    "EN ISO 13849-2": "Validazione delle parti dei sistemi di comando legate alla sicurezza progettate con la "
    "EN ISO 13849-1: piano di validazione, analisi e prove, elenchi di guasti da considerare e principi di "
    "sicurezza ben provati per tecnologia meccanica, pneumatica, idraulica ed elettrica.",
    "EN IEC 62061": "Sicurezza funzionale dei sistemi di comando legati alla sicurezza (alternativa alla "
    "EN ISO 13849-1): specifica delle funzioni di sicurezza, livello di integrità SIL richiesto, architetture dei "
    "sottosistemi e verifica. Adatta soprattutto a sistemi elettrici ed elettronici programmabili complessi.",
    "EN 60204-1": "Equipaggiamento elettrico delle macchine: alimentazione e sezionatore generale, protezione contro "
    "la scossa elettrica e le sovracorrenti, collegamenti equipotenziali, funzioni di comando e arresto (categorie "
    "0, 1, 2), arresto di emergenza, dispositivi di comando, quadri, cavi, marcatura e documentazione elettrica.",
    "EN IEC 61439-1": "Quadri elettrici di bassa tensione: regole generali di progetto e verifica (sovratemperature, "
    "tenuta al cortocircuito, distanze di isolamento, grado di protezione). Da richiamare per il quadro elettrico "
    "insieme alla EN 60204-1.",
    "EN ISO 13850": "Funzione di arresto di emergenza: requisiti funzionali e di progetto del dispositivo (fungo "
    "rosso su fondo giallo, azione di aggancio, ripristino manuale che non riavvia la macchina), categoria di "
    "arresto 0 o 1, posizionamento e raggiungibilità dalle postazioni.",
    "EN ISO 14118": "Prevenzione dell'avviamento inatteso: isolamento e dissipazione delle energie (elettrica, "
    "pneumatica, idraulica, meccanica, gravità), dispositivi di sezionamento lucchettabili e misure per impedire "
    "riavvii durante gli interventi di manutenzione, regolazione e pulizia.",
    "EN ISO 14119": "Dispositivi di interblocco associati ai ripari: tipi di dispositivo (da 1 a 4), interblocco con "
    "e senza bloccaggio, scelta in base al tempo di arresto, misure contro l'elusione, sblocco di fuga e di "
    "emergenza. Da richiamare per ogni porta o riparo mobile interbloccato.",
    "EN ISO 14120": "Ripari: requisiti generali di progetto e costruzione dei ripari fissi e mobili (robustezza, "
    "materiali, visibilità attraverso il riparo, contenimento di pezzi proiettati, fissaggi che richiedono un "
    "attrezzo, aperture e loro dimensioni) e criteri di scelta del tipo di riparo.",
    "EN ISO 13857": "Distanze di sicurezza per impedire il raggiungimento delle zone pericolose con arti superiori e "
    "inferiori: tabelle in funzione dell'altezza della zona e della barriera, delle aperture nei ripari e del "
    "passaggio sotto i ripari.",
    "EN ISO 13854": "Spazi minimi tra parti mobili e fisse per evitare lo schiacciamento delle parti del corpo "
    "(corpo, testa, braccio, mano, dita, piede). Si applica dove il pericolo si evita con lo spazio invece che con "
    "un riparo.",
    "EN ISO 13855": "Posizionamento dei mezzi di protezione rispetto alla velocità di avvicinamento del corpo: "
    "calcolo della distanza minima di barriere fotoelettriche, scanner, tappeti sensibili e comandi a due mani in "
    "funzione del tempo di arresto complessivo della macchina.",
    "EN IEC 61496-1": "Apparecchi elettrosensibili di protezione (barriere fotoelettriche, scanner laser): requisiti "
    "generali, tipi 2, 3 e 4, comportamento in caso di guasto e prove. Il tipo va scelto in coerenza con il PLr "
    "della funzione di sicurezza.",
    "EN ISO 10218-1": "Robot industriali: requisiti di sicurezza per la progettazione del robot (arresti, velocità "
    "ridotta, dispositivo di abilitazione, limitazione dello spazio, funzioni collaborative). Interessa le celle "
    "con robot di carico e scarico.",
    "EN ISO 10218-2": "Applicazioni e celle robotizzate: integrazione del robot nell'impianto, layout e spazi, "
    "protezioni perimetrali, modi di funzionamento, programmazione e manutenzione in sicurezza, interfacce con le "
    "altre macchine della cella.",
    "EN ISO 11161": "Sistemi di fabbricazione integrati (insiemi di macchine): valutazione del rischio dell'intero "
    "impianto, suddivisione in zone, arresti e arresti di emergenza tra macchine collegate, modi di funzionamento e "
    "interventi in una zona con le altre in marcia.",
    "EN ISO 16089": "Norma di tipo C per le macchine utensili rettificatrici fisse: pericoli specifici (rottura e "
    "proiezione della mola, contatto con l'utensile, refrigerante, polveri) e misure di protezione richieste. "
    "Verificare che il campo di applicazione copra la macchina della commessa.",
    "EN 13743": "Prodotti abrasivi rivestiti (nastri, dischi in tela o carta): requisiti di sicurezza, marcatura e "
    "velocità massime di impiego. Da richiamare per le unità a nastro abrasivo.",
    "EN ISO 4414": "Trasmissioni pneumatiche: regole generali e requisiti di sicurezza per impianti e componenti "
    "(pressioni, sezionamento e scarico, comportamento in caso di caduta o ritorno dell'aria, tubazioni e "
    "silenziatori).",
    "EN ISO 14122-2": "Mezzi di accesso permanenti alle macchine: piattaforme di lavoro e passerelle (dimensioni, "
    "portata, pavimentazione antiscivolo, altezza libera).",
    "EN ISO 14122-3": "Mezzi di accesso permanenti alle macchine: scale, scale a castello e parapetti (pendenze, "
    "pedate, corrimano, altezza e struttura dei parapetti).",
    "EN 1837": "Illuminazione integrata nelle macchine: livelli di illuminamento nelle zone di lavoro, regolazione e "
    "manutenzione, abbagliamento ed effetto stroboscopico.",
    "EN 614-1": "Principi ergonomici di progettazione: interazione tra operatore e macchina, postura, movimenti, "
    "dispositivi di segnalazione e comando, carico di lavoro fisico e mentale.",
    "EN 1005-2": "Prestazione fisica umana: limiti raccomandati per la movimentazione manuale di macchine e "
    "componenti (sollevamento, trasporto), utile per il carico manuale dei pezzi.",
    "EN ISO 14738": "Requisiti antropometrici per i posti di lavoro alle macchine: dimensioni, altezze di lavoro, "
    "spazi per le gambe e zone di raggiungimento per lavoro in piedi e seduto.",
    "EN 61310-1": "Indicazione, marcatura e manovra: requisiti per segnali visivi, acustici e tattili (colori delle "
    "spie e dei pulsanti, segnalazioni di pericolo e di stato della macchina).",
    "EN ISO 7010": "Segni grafici: segnali di sicurezza registrati (avvertimento, divieto, obbligo, salvataggio) con "
    "forma, colori e pittogrammi da usare sulla macchina e nel manuale.",
    "EN ISO 20607": "Manuale di istruzioni: principi generali di stesura, struttura e contenuti minimi (uso "
    "previsto, installazione, uso, manutenzione, rischi residui), comprensibilità e lingue.",
    "EN ISO 11688-1": "Progettazione di macchine a bassa rumorosità: pianificazione e misure di riduzione del rumore "
    "alla fonte (sorgenti, trasmissione, cabine e silenziatori).",
    "EN ISO 3744": "Determinazione del livello di potenza sonora con misure di pressione su una superficie che "
    "avvolge la macchina (metodo tecnico progettuale). Serve per i valori di rumore da dichiarare nel manuale.",
    "EN ISO 11202": "Misura del livello di pressione sonora di emissione al posto di lavoro e in altre posizioni "
    "specificate, dato da dichiarare nel manuale.",
    "EN ISO 4871": "Dichiarazione e verifica dei valori di emissione sonora delle macchine (valori dichiarati, "
    "incertezza, forma della dichiarazione nel manuale e nella documentazione commerciale).",
    "EN ISO 13732-1": "Superfici calde: valori soglia di ustione al contatto in funzione della temperatura, del "
    "materiale e della durata del contatto, per decidere se servono protezioni o avvertenze.",
    "EN ISO 19353": "Prevenzione e protezione contro l'incendio delle macchine: identificazione dei pericoli di "
    "incendio (materiali, polveri, scintille), misure di prevenzione e, dove serve, sistemi di rilevazione e "
    "spegnimento.",
    "EN 1127-1": "Atmosfere esplosive: prevenzione dell'esplosione e protezione, concetti e metodi di base "
    "(sorgenti di innesco, zone, misure costruttive). Rilevante con polveri combustibili prodotte dalla lavorazione.",
    "EN ISO 14123-1": "Riduzione dei rischi per la salute derivanti da sostanze pericolose emesse dalle macchine "
    "(polveri, nebbie, fumi): principi e specifiche per i costruttori, captazione alla fonte e aspirazione.",
    "EN IEC 62443-3-3": "Sicurezza informatica dei sistemi di automazione industriale: requisiti di sicurezza del "
    "sistema e livelli di sicurezza (accessi, autenticazione, integrità, segmentazione della rete). Riferimento "
    "per la protezione dall'alterazione dei sistemi di comando (RESS 1.1.9).",
}
