"""Proposta dei testi di una scheda (modello o della commessa) scritta da Claude.

Il pulsante "Proponi testi" manda i dati della scheda così come sono nella pagina (anche non salvati);
qui si prepara la richiesta con requisito, modulo, pericoli, metodo di stima e alcune schede della libreria
come esempio di stile, e si restituiscono i testi proposti. Niente viene salvato: il tecnico rilegge,
corregge e salva.

Serve la chiave dell'API di Anthropic nella variabile d'ambiente ANTHROPIC_API_KEY del server, e il server
deve poter raggiungere internet (api.anthropic.com)."""

import json
import os

from . import models as m
from .testo import semplice

MODELLO = "claude-opus-5-5"

CAMPI_TESTO = (
    "zona_pericolosa",
    "considerazioni_pericoli",
    "considerazioni_limiti",
    "considerazioni_soggetti",
    "considerazioni_stima_iniziale",
    "considerazioni_riduzione",
    "considerazioni_stima_finale",
    "testo_istruzioni",
)
FATTORI = ("se", "fr", "pr", "av")
VALORI = {"se": [1, 2, 3, 4], "fr": [2, 3, 4, 5], "pr": [1, 2, 3, 4, 5], "av": [1, 3, 5]}

_TESTO = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "zona_impianto": _TESTO,
        **{campo: _TESTO for campo in CAMPI_TESTO},
        **{f"{f}_{fase}": {"type": "integer", "enum": VALORI[f]} for fase in ("iniziale", "finale") for f in FATTORI},
        "misure": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"tipo": {"type": "string", "enum": ["PROG", "PROT", "INFO"]}, "testo": _TESTO},
                "required": ["tipo", "testo"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "zona_impianto", *CAMPI_TESTO, *(f"{f}_{fase}" for fase in ("iniziale", "finale") for f in FATTORI), "misure",
    ],
    "additionalProperties": False,
}

ISTRUZIONI = """Sei un tecnico esperto di sicurezza macchine che lavora per C.O.S.M.A.P. s.r.l. (Saccolongo, PD), \
costruttore di macchine e impianti di smerigliatura, lucidatura e satinatura di componenti metallici (rubinetteria, \
articoli sanitari, maniglie, componenti automotive). Compili le schede dell'analisi dei rischi secondo il \
Regolamento (UE) 2023/1230 (Allegato III, RESS) e la EN ISO 12100, con il metodo di stima ISO/TR 14121-2 ibrido.

Ogni scheda tratta un requisito RESS per un modulo della macchina. Scrivi in italiano tecnico, chiaro e completo, \
con un tono da relazione tecnica che un ispettore o un cliente leggerà. I testi devono essere ricchi e articolati: \
spiega il perché delle scelte, cita le situazioni operative concrete (produzione automatica, carico e scarico, \
cambio utensile o spazzola, regolazione, pulizia, manutenzione, ricerca guasti), i soggetti coinvolti e le norme \
pertinenti (es. EN ISO 12100, EN ISO 13849-1, EN ISO 14120, EN ISO 14119, EN ISO 13857, EN 60204-1, EN ISO 16089, \
EN ISO 10218-2) quando servono davvero.

Formato dei testi: testo semplice; puoi usare <b>…</b> per evidenziare e <ul><li>…</li></ul> per gli elenchi. \
Niente altri tag, niente markdown, niente titoli.

Cosa scrivere in ogni campo:
- zona_impianto: nome breve della zona dell'impianto (preferisci uno di quelli già usati in libreria, se adatto).
- zona_pericolosa: dove si trova il pericolo, in una o due frasi.
- considerazioni_pericoli: quali pericoli genera la zona, con quale meccanismo e quali conseguenze (4-6 frasi).
- considerazioni_limiti: limiti della macchina, uso previsto e uso scorretto ragionevolmente prevedibile, \
fasi di vita in cui il pericolo si presenta (4-6 frasi).
- considerazioni_soggetti: chi è esposto (operatore, manutentore, addetto alla pulizia, altre persone nell'area) \
e in quali momenti (3-5 frasi).
- se/fr/pr/av iniziale: stima SENZA le misure di protezione.
- considerazioni_stima_iniziale: motiva ogni fattore (Se, Fr, Pr, Av) richiamando la scala del metodo (4-6 frasi).
- considerazioni_riduzione: strategia di riduzione secondo il metodo in tre passi della EN ISO 12100 \
(progettazione, protezioni, informazioni) (4-6 frasi).
- misure: da 4 a 7 misure, nell'ordine progettazione (PROG), protezione e misure complementari (PROT), \
informazioni per l'uso (INFO); ogni misura è descritta in 2-4 frasi concrete, con le norme di riferimento.
- se/fr/pr/av finale: stima CON le misure. Regole del metodo COSMAP: Fr finale = Fr iniziale (la frequenza reale \
di esposizione non cambia); Se finale si abbassa solo se la protezione limita davvero il danno, altrimenti resta \
uguale; Pr e Av si riducono in base alle misure.
- considerazioni_stima_finale: motiva la stima finale e l'esito della matrice (4-6 frasi).
- testo_istruzioni: rischio residuo e indicazioni per il manuale di istruzioni (avvertenze, DPI, formazione, \
procedure), con un elenco puntato quando aiuta (5-8 frasi o punti).

Quando un dato della macchina non è noto, scrivi una formulazione generale valida per le macchine COSMAP del modulo; \
non inventare valori numerici precisi (velocità, distanze, tempi) che non conosci."""


class PropostaNonDisponibile(Exception):
    """Messaggio da mostrare al tecnico quando la proposta non si può avere."""


def _testo(valore):
    return semplice(valore or "").strip()


def _metodo():
    metodo = m.MetodoStima.corrente()
    if not metodo:
        return ""
    righe = [f"Metodo di stima: {metodo.versione}. Cl = Fr + Pr + Av."]
    for (fattore, valore), descrizione in sorted(metodo.descrizioni().items(), key=lambda v: (v[0][0], -v[0][1])):
        righe.append(f"- {fattore} {valore}: {descrizione}")
    righe.append("Matrice (Se, fascia di Cl -> esito):")
    for cella in metodo.celle.select_related("fascia").order_by("-se", "fascia__cl_min"):
        righe.append(f"- Se {cella.se}, Cl {cella.fascia.cl_min}-{cella.fascia.cl_max}: {cella.get_esito_display()}")
    return "\n".join(righe)


def _descrivi_scheda(s, misure):
    righe = [
        f"Scheda {s.codice} – modulo {s.modulo.nome}, requisito {s.requisito.codice} {s.requisito.titolo}",
        f"Zona dell'impianto: {s.zona_impianto}",
    ]
    for campo in CAMPI_TESTO:
        valore = _testo(getattr(s, campo))
        if valore:
            righe.append(f"{campo}: {valore}")
    stime = [f"{f}_{fase}={getattr(s, f'{f}_{fase}')}" for fase in ("iniziale", "finale") for f in FATTORI]
    righe.append("Stime: " + ", ".join(stime))
    for misura in misure:
        righe.append(f"Misura {misura.tipo}: {_testo(misura.testo)}")
    return "\n".join(righe)


def _esempi(modulo, requisito, escludi=None, quanti=3):
    """Schede modello già compilate, come esempio di stile: prima dello stesso modulo, poi dello stesso requisito."""
    compilate = m.SchedaModello.objects.exclude(considerazioni_riduzione="").exclude(pk=escludi)
    scelte = []
    for filtro in ({"modulo": modulo}, {"requisito": requisito}, {}):
        if None in filtro.values():
            continue
        for s in compilate.filter(**filtro).select_related("modulo", "requisito").order_by("-stato", "codice"):
            if s not in scelte:
                scelte.append(s)
            if len(scelte) >= quanti:
                return scelte
    return scelte


def richiesta(dati):
    """Testo della richiesta a Claude dai dati della scheda nella pagina (vedi views.proponi_testi)."""
    requisito, modulo = dati["requisito"], dati["modulo"]
    parti = [
        "## Scheda da compilare",
        f"Modulo: {modulo.nome}" + (f" ({modulo.sigla})" if modulo.sigla else "") if modulo else "Modulo: non indicato",
    ]
    if modulo and modulo.descrizione:
        parti.append(f"Descrizione del modulo: {_testo(modulo.descrizione)}")
    if requisito:
        parti.append(f"Requisito RESS: {requisito.codice} {requisito.titolo}")
        if requisito.descrizione:
            parti.append(f"Testo del requisito (Allegato III): {_testo(requisito.descrizione)}")
    if dati["pericoli"]:
        parti.append("Pericoli scelti (EN ISO 12100, allegato B): " + "; ".join(str(p) for p in dati["pericoli"]))
    if dati["condizioni"]:
        parti.append("Condizioni operative: " + ", ".join(str(c) for c in dati["condizioni"]))
    if dati["soggetti"]:
        parti.append("Soggetti esposti: " + ", ".join(str(f) for f in dati["soggetti"]))
    if dati.get("macchina"):
        parti.append(f"Macchina della commessa: {dati['macchina']}")
    gia_scritti = {campo: _testo(dati["testi"].get(campo)) for campo in ("zona_impianto", *CAMPI_TESTO)}
    gia_scritti = {campo: valore for campo, valore in gia_scritti.items() if valore}
    if gia_scritti or dati["misure"]:
        parti.append("\nTesti già scritti dal tecnico: tienine conto, riprendine il contenuto e ampliali.")
        parti += [f"{campo}: {valore}" for campo, valore in gia_scritti.items()]
        parti += [f"Misura: {_testo(testo)}" for testo in dati["misure"] if _testo(testo)]
    zone = sorted(set(m.SchedaModello.objects.exclude(zona_impianto="").values_list("zona_impianto", flat=True)))
    if zone:
        parti.append("\nZone dell'impianto già usate in libreria: " + "; ".join(zone))
    parti.append("\n## Metodo di stima\n" + _metodo())
    esempi = _esempi(modulo, requisito, dati.get("escludi"))
    if esempi:
        parti.append("\n## Schede della libreria COSMAP come esempio di contenuto e terminologia")
        for s in esempi:
            parti.append("\n" + _descrivi_scheda(s, s.misure.order_by("ordine", "pk")))
    parti.append(
        "\nScrivi la proposta completa per la scheda da compilare. Sii generoso e dettagliato nei testi: "
        "più ampi e argomentati degli esempi, che servono solo per lo stile e la terminologia."
    )
    return "\n".join(parti)


def _chiama(testo_richiesta):
    """Chiamata all'API di Anthropic; restituisce il JSON della proposta (dict)."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise PropostaNonDisponibile(
            "Manca la chiave dell'API di Claude: impostare la variabile d'ambiente ANTHROPIC_API_KEY sul server "
            "e riavviare il programma."
        )
    import anthropic

    client = anthropic.Anthropic(timeout=600)
    try:
        # Streaming: con il ragionamento la risposta può essere lunga e superare il tempo di una richiesta semplice.
        # fallbacks="default": se Claude rifiuta la richiesta, l'API riprova da sola con il modello consigliato.
        with client.beta.messages.stream(
            model=MODELLO,
            max_tokens=32000,
            system=ISTRUZIONI,
            messages=[{"role": "user", "content": testo_richiesta}],
            thinking={"type": "adaptive"},
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
            fallbacks="default",
            betas=["server-side-fallback-2026-07-01"],
        ) as stream:
            risposta = stream.get_final_message()
    except anthropic.APIConnectionError:
        raise PropostaNonDisponibile("Il server non riesce a collegarsi a Claude: controllare l'accesso a internet.")
    except anthropic.AuthenticationError:
        raise PropostaNonDisponibile("La chiave dell'API di Claude (ANTHROPIC_API_KEY) non è valida.")
    except anthropic.RateLimitError:
        raise PropostaNonDisponibile("Troppe richieste a Claude in poco tempo: riprovare tra qualche minuto.")
    except anthropic.APIStatusError as e:
        raise PropostaNonDisponibile(f"Claude non ha risposto ({e.status_code}): riprovare più tardi.")
    if risposta.stop_reason == "refusal":
        raise PropostaNonDisponibile("Claude non ha scritto la proposta per questa scheda.")
    if risposta.stop_reason == "max_tokens":
        raise PropostaNonDisponibile("La proposta è venuta troppo lunga ed è stata interrotta: riprovare.")
    testi = [b.text for b in risposta.content if b.type == "text"]
    if not testi:
        raise PropostaNonDisponibile("Claude non ha restituito testi: riprovare.")
    return json.loads(testi[-1])


def proponi(dati):
    """Proposta per la scheda: testi, stime e misure. Applica le regole del metodo sulle stime finali."""
    if not dati["requisito"]:
        raise PropostaNonDisponibile("Scegli prima il requisito RESS della scheda.")
    proposta = _chiama(richiesta(dati))
    # Regole del metodo COSMAP: Fr finale = Fr reale; Se finale non supera quella iniziale.
    proposta["fr_finale"] = proposta.get("fr_iniziale")
    if proposta.get("se_iniziale") and proposta.get("se_finale"):
        proposta["se_finale"] = min(proposta["se_finale"], proposta["se_iniziale"])
    proposta["zona_impianto"] = (proposta.get("zona_impianto") or "")[:60]
    return proposta
