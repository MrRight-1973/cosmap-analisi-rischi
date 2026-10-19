"""Grafico del PL raggiunto (EN ISO 13849-1, tabella 2): fasce PL a–e sulla scala logaritmica del PFH, con la
funzione (percorso peggiore), i percorsi e i sottosistemi. I PFH sono in 10⁻⁹/h, come nel motore di calcolo."""

import math
from xml.sax.saxutils import escape

# Limiti delle fasce in 10⁻⁹/h: PL a 10⁻⁵…10⁻⁴, b 3·10⁻⁶…10⁻⁵, c 10⁻⁶…3·10⁻⁶, d 10⁻⁷…10⁻⁶, e 10⁻⁸…10⁻⁷
FASCE = [("a", 10000, 100000), ("b", 3000, 10000), ("c", 1000, 3000), ("d", 100, 1000), ("e", 10, 100)]
COLORI = {"a": "#F4C7C3", "b": "#F9D9B8", "c": "#FBEBB5", "d": "#D9EBC6", "e": "#BFE3C6"}
MASSIMO, MINIMO = 100000, 10  # estremi della scala (sinistra peggiore, destra migliore)

ETICHETTA = 250  # larghezza della colonna dei nomi
LARGHEZZA = 460  # larghezza della scala
VALORI = 170  # colonna dei valori, a destra della scala
RIGA = 22
SOPRA = 46


def _x(pfh):
    pfh = min(max(pfh, MINIMO), MASSIMO)
    return ETICHETTA + (math.log10(MASSIMO) - math.log10(pfh)) / (math.log10(MASSIMO) - math.log10(MINIMO)) * LARGHEZZA


def _pfh_testo(pfh):
    """10⁻⁹/h -> notazione con potenza di dieci, es. 52,7 -> 5,27·10⁻⁸/h."""
    if pfh is None:
        return "–"
    valore = pfh * 1e-9
    esponente = math.floor(math.log10(valore)) if valore > 0 else 0
    mantissa = valore / 10 ** esponente
    apici = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
    return f"{mantissa:.2f}".replace(".", ",") + "·10" + str(esponente).translate(apici) + "/h"


def svg(pl, pfh, plr, percorsi=(), sottosistemi=()):
    """SVG del grafico. percorsi e sottosistemi: elenchi di dizionari con nome, pfh, pl (come dal motore)."""
    righe = [("Funzione (percorso peggiore)", pfh, pl, "funzione")]
    if len(percorsi) > 1:
        righe += [(f"Percorso {p.get('nome') or '–'}", p.get("pfh"), p.get("pl"), "percorso") for p in percorsi]
    righe += [
        (f"{s.get('nome') or 'Sottosistema'}" + (f" · {s['percorso']}" if s.get("percorso") else ""), s.get("pfh"), s.get("pl"), "sottosistema")
        for s in sottosistemi
    ]
    altezza = SOPRA + len(righe) * RIGA + 34
    parti = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ETICHETTA + LARGHEZZA + VALORI} {altezza}" '
        f'class="grafico-pl" role="img" aria-label="PL raggiunto {escape(pl or "–")}, PLr {escape(plr or "–")}">'
    ]
    fondo = SOPRA + len(righe) * RIGA
    for lettera, basso, alto in FASCE:
        x1, x2 = _x(alto), _x(basso)
        richiesto = plr and lettera == plr
        parti.append(
            f'<rect x="{x1:.1f}" y="{SOPRA - 18}" width="{x2 - x1:.1f}" height="{fondo - SOPRA + 18}" fill="{COLORI[lettera]}"'
            + (' stroke="#1F4E79" stroke-width="2.5"' if richiesto else "") + "/>"
        )
        parti.append(
            f'<text x="{(x1 + x2) / 2:.1f}" y="{SOPRA - 24}" text-anchor="middle" font-size="12" font-weight="bold">PL {lettera}'
            + (" (PLr)" if richiesto else "") + "</text>"
        )
    parti.append(f'<text x="{ETICHETTA + LARGHEZZA + 12}" y="{SOPRA - 24}" font-size="12" font-weight="bold">PL · PFH</text>')
    # Limite di accettazione: il PFH deve stare a destra del limite inferiore della fascia del PLr
    if plr:
        limite = next(alto for lettera, basso, alto in FASCE if lettera == plr)
        x = _x(limite)
        parti.append(f'<line x1="{x:.1f}" y1="{SOPRA - 18}" x2="{x:.1f}" y2="{fondo}" stroke="#1F4E79" stroke-width="2" stroke-dasharray="4 3"/>')
    for i, (nome, valore, livello, tipo) in enumerate(righe):
        y = SOPRA + i * RIGA + RIGA / 2
        peso = "bold" if tipo == "funzione" else "normal"
        rientro = {"funzione": 4, "percorso": 14, "sottosistema": 24}[tipo]
        parti.append(f'<line x1="{ETICHETTA}" y1="{y:.1f}" x2="{ETICHETTA + LARGHEZZA}" y2="{y:.1f}" stroke="#9AA3AE" stroke-width="0.5"/>')
        parti.append(
            f'<text x="{rientro}" y="{y + 4:.1f}" font-size="11.5" font-weight="{peso}">{escape(nome[:38])}</text>'
        )
        if valore is None:
            parti.append(f'<text x="{ETICHETTA + 6}" y="{y + 4:.1f}" font-size="11" fill="#5F6B7A">non calcolabile</text>')
            continue
        x = _x(valore)
        raggio = 7 if tipo == "funzione" else 5
        colore = "#1F4E79" if tipo == "funzione" else "#4A5563"
        parti.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{raggio}" fill="{colore}"/>')
        testo = f"PL {livello or '–'} · {_pfh_testo(valore)}"
        parti.append(
            f'<text x="{ETICHETTA + LARGHEZZA + 12}" y="{y + 4:.1f}" font-size="11" font-weight="{peso}">{escape(testo)}</text>'
        )
    # Scala del PFH
    for valore in (100000, 10000, 1000, 100, 10):
        x = _x(valore)
        parti.append(f'<line x1="{x:.1f}" y1="{fondo}" x2="{x:.1f}" y2="{fondo + 5}" stroke="#5F6B7A"/>')
        parti.append(f'<text x="{x:.1f}" y="{fondo + 17}" text-anchor="middle" font-size="10" fill="#5F6B7A">{_pfh_testo(valore)}</text>')
    parti.append(
        f'<text x="{ETICHETTA + LARGHEZZA}" y="{fondo + 30}" text-anchor="end" font-size="10" fill="#5F6B7A">'
        "PFH (probabilità di guasto pericoloso per ora): verso destra è meglio</text>"
    )
    parti.append("</svg>")
    return "".join(parti)
