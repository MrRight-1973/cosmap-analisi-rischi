"""Funzioni di sicurezza tipo Cosmap, proposte nelle commesse che hanno il modulo.

S, F e P sono una proposta (EN ISO 13849-1, allegato A); schema a blocchi e componenti si completano con il
calcolo del PL e, quando la funzione è collaudata, si salva di nuovo come funzione tipo dalla sua pagina.
"""

NOTA = "Funzione tipo Cosmap: S, F e P proposti; schema a blocchi e componenti da completare con il calcolo del PL."

# (nome, sigle del modulo in ordine di preferenza o None per tutte le macchine, S, F, P, descrizione).
# TAV è la tavola rotante a scatti (macchine TR, le più comuni), TRC la tavola in continuo: le funzioni della tavola
# vanno su TAV e, se la libreria non lo ha, su TRC. CSM resta per una libreria con un modulo della stazione di carico.
FUNZIONI_TIPO = [
    ("Arresto di emergenza", None, "S2", "F1", "P2",
     "Evento: pressione di un pulsante di emergenza (pulpito, stazione di carico, porte). Reazione: arresto di "
     "categoria 0 o 1 di tutti i movimenti pericolosi. Stato sicuro: macchina ferma, riavvio solo dopo il "
     "ripristino del pulsante e un comando volontario."),
    ("Arresto all'apertura delle porte interbloccate", "CAB", "S2", "F1", "P2",
     "Evento: apertura di una porta della cabina. Reazione: arresto dei movimenti pericolosi della zona. "
     "Stato sicuro: movimenti fermi finché la porta è aperta; la chiusura non riavvia la macchina."),
    ("Bloccaggio delle porte fino all'arresto dei movimenti", "CAB", "S2", "F1", "P2",
     "Evento: richiesta di accesso alla cabina. Reazione: le porte restano bloccate finché utensili e assi non "
     "sono fermi (arresto per inerzia sorvegliato o temporizzato). Stato sicuro: accesso solo a movimenti fermi."),
    ("Barriera di protezione della stazione di carico", ("CSM", "TAV"), "S2", "F2", "P1",
     "Evento: interruzione della barriera alla stazione di carico. Reazione: arresto della rotazione della tavola. "
     "Stato sicuro: tavola ferma con l'operatore nella zona di carico; ripristino manuale dall'esterno."),
    ("Consenso alla rotazione della tavola", ("TAV", "TRC"), "S2", "F2", "P1",
     "Evento: comando di rotazione della tavola. Reazione: la rotazione parte solo con la barriera libera e il "
     "consenso di presenza operatore fuori zona dato da HMI. Stato sicuro: tavola ferma senza consenso."),
    ("Arresto su perdita di vuoto delle attrezzature", ("TAV", "TRC"), "S2", "F2", "P1",
     "Evento: calo del vuoto su una stazione (vacuostato). Reazione: arresto delle unità di lavoro e della "
     "tavola. Stato sicuro: nessuna lavorazione su un pezzo non trattenuto."),
    ("Barriera della zona di carico pallet", "PAL", "S2", "F2", "P1",
     "Evento: interruzione della barriera della zona di carico. Reazione: arresto dello scambio pallet. "
     "Stato sicuro: pallet fermi con l'operatore nella zona; ripristino manuale dall'esterno."),
    ("Velocità ridotta e dispositivo di abilitazione in modo manuale", "ROB", "S2", "F1", "P1",
     "Evento: robot in modo manuale con la cella aperta. Reazione: velocità limitata (≤ 250 mm/s) sorvegliata e "
     "movimento solo con il dispositivo di abilitazione premuto. Stato sicuro: arresto al rilascio o al "
     "superamento della velocità."),
]


def crea(FunzioneTipo, Modulo):
    """Crea le funzioni tipo mancanti. Quelle di un modulo si creano solo se il modulo (cercato per sigla) esiste:
    altrimenti verrebbero proposte a tutte le macchine. Si può rilanciare: non duplica e non tocca quelle esistenti."""
    create = 0
    for ordine, (nome, sigle, s, f, p, descrizione) in enumerate(FUNZIONI_TIPO, start=1):
        if isinstance(sigle, str):
            sigle = (sigle,)
        modulo = next((m for m in (Modulo.objects.filter(sigla=x).first() for x in sigle or ()) if m), None)
        if sigle and modulo is None:
            continue
        _, nuova = FunzioneTipo.objects.get_or_create(
            nome=nome,
            defaults={"modulo": modulo, "s": s, "f": f, "p": p, "descrizione": descrizione, "note": NOTA, "ordine": ordine * 10},
        )
        create += nuova
    return create
