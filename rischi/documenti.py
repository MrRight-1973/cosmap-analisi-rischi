"""Generazione dei documenti PDF di una revisione.

- Dichiarazione UE di conformità (Regolamento (UE) 2023/1230, Allegato V parte A)
- Valutazione dei rischi
- Elenco dei rischi residui per il manuale
- Relazione sulle funzioni di sicurezza (EN ISO 13849-1/-2), con flusso di approvazione della validazione

I testi fissi della dichiarazione vanno confrontati con il testo ufficiale del
Regolamento prima dell'uso: l'applicazione struttura il documento, la
responsabilità resta di chi firma.
"""

import io
import re
from itertools import groupby
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus.flowables import _listWrapOn
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.platypus import (
    Image,
    CondPageBreak,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String

from . import calcolo
from .models import (
    ArticoloSicurezza,
    CapitoloValutazione,
    Esito,
    Fabbricante,
    Norma,
    Revisione,
    SchedaAnalisi,
    SoluzioneProtezione,
    ValidazioneSicurezza,
    VerificaElettrica,
)
from .testo import e_formattato, in_reportlab

REGOLAMENTO = "Regolamento (UE) 2023/1230"

TESTI = {
    "it": {
        "titolo": "Dichiarazione UE di conformità",
        "sottotitolo": "Regolamento (UE) 2023/1230 relativo alle macchine, Allegato V, parte A",
        "numero": "N.",
        "fabbricante": "Fabbricante",
        "piva": "Partita IVA",
        "fascicolo": "Persona autorizzata a costituire la documentazione tecnica",
        "responsabilita": (
            "La presente dichiarazione di conformità è rilasciata sotto la responsabilità esclusiva del fabbricante."
        ),
        "oggetto": "Oggetto della dichiarazione",
        "denominazione": "Denominazione",
        "funzione": "Funzione",
        "modello": "Modello / tipo",
        "matricola": "Numero di serie",
        "anno": "Anno di costruzione",
        "conforme": (
            "L'oggetto della dichiarazione sopra descritto è conforme a tutte le disposizioni pertinenti del "
            "Regolamento (UE) 2023/1230 relativo alle macchine"
        ),
        "conforme_altre": " e alla seguente normativa di armonizzazione dell'Unione:",
        "norme_arm": "Norme armonizzate applicate",
        "norme_altre": "Altre norme e specifiche tecniche applicate",
        "organismo": "Organismo notificato",
        "firmato": "Firmato a nome e per conto di",
        "luogo_data": "Luogo e data",
        "nome_qualifica": "Nome e qualifica",
        "firma": "Firma",
        "bozza": "BOZZA – revisione non approvata, documento non valido",
        "pagina": "Pagina",
    },
    "en": {
        "titolo": "EU Declaration of Conformity",
        "sottotitolo": "Regulation (EU) 2023/1230 on machinery, Annex V, Part A",
        "numero": "No.",
        "fabbricante": "Manufacturer",
        "piva": "VAT number",
        "fascicolo": "Person authorised to compile the technical documentation",
        "responsabilita": "This declaration of conformity is issued under the sole responsibility of the manufacturer.",
        "oggetto": "Object of the declaration",
        "denominazione": "Name",
        "funzione": "Function",
        "modello": "Model / type",
        "matricola": "Serial number",
        "anno": "Year of construction",
        "conforme": (
            "The object of the declaration described above is in conformity with all the relevant provisions of "
            "Regulation (EU) 2023/1230 on machinery"
        ),
        "conforme_altre": " and with the following Union harmonisation legislation:",
        "norme_arm": "Harmonised standards applied",
        "norme_altre": "Other standards and technical specifications applied",
        "organismo": "Notified body",
        "firmato": "Signed for and on behalf of",
        "luogo_data": "Place and date",
        "nome_qualifica": "Name and function",
        "firma": "Signature",
        "bozza": "DRAFT – revision not approved, document not valid",
        "pagina": "Page",
    },
}

ESITI_TESTO = {Esito.OK: "OK", Esito.SUGGERITE: "Misure suggerite", Esito.RICHIESTE: "Misure richieste"}
ESITI_COLORE = {Esito.OK: "#E6F4E7", Esito.SUGGERITE: "#FFF6D6", Esito.RICHIESTE: "#FDE8E6"}

# ---------------------------------------------------------------------------
# Carattere: un TrueType con tutti i simboli (≤, ≥, …) se disponibile,
# altrimenti Helvetica con i soli caratteri dell'Europa occidentale.
# ---------------------------------------------------------------------------

_CARATTERI_CANDIDATI = [
    # normale, grassetto, corsivo, grassetto corsivo
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/ariali.ttf", "C:/Windows/Fonts/arialbi.ttf"),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
    ),
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    ),
    (
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-BoldOblique.ttf",
    ),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf", "/Library/Fonts/Arial Italic.ttf", "/Library/Fonts/Arial Bold Italic.ttf"),
]
_carattere = None


def _carattere_registrato():
    """(normale, grassetto, unicode completo) – registra il carattere una sola volta.

    Si preferisce una famiglia con anche il corsivo; senza, il corsivo esce come testo normale.
    """
    global _carattere
    if _carattere is None:
        _carattere = ("Helvetica", "Helvetica-Bold", False)
        presenti = [c for c in _CARATTERI_CANDIDATI if Path(c[0]).exists() and Path(c[1]).exists()]
        presenti.sort(key=lambda c: not all(Path(f).exists() for f in c))
        if presenti:
            normale, grassetto, corsivo, grassetto_corsivo = presenti[0]
            pdfmetrics.registerFont(TTFont("Testo", normale))
            pdfmetrics.registerFont(TTFont("Testo-Grassetto", grassetto))
            nomi = {"normal": "Testo", "bold": "Testo-Grassetto", "italic": "Testo", "boldItalic": "Testo-Grassetto"}
            if Path(corsivo).exists() and Path(grassetto_corsivo).exists():
                pdfmetrics.registerFont(TTFont("Testo-Corsivo", corsivo))
                pdfmetrics.registerFont(TTFont("Testo-GrassettoCorsivo", grassetto_corsivo))
                nomi.update(italic="Testo-Corsivo", boldItalic="Testo-GrassettoCorsivo")
            pdfmetrics.registerFontFamily("Testo", **nomi)
            _carattere = ("Testo", "Testo-Grassetto", True)
    return _carattere


def _pulito(testo):
    """Testo sicuro per i paragrafi: caratteri speciali, a capo e formattazione delle schede."""
    testo = "" if testo is None else str(testo)
    if not _carattere_registrato()[2]:
        testo = testo.replace("≤", "<=").replace("≥", ">=").encode("cp1252", "replace").decode("cp1252")
    if e_formattato(testo):  # testo dell'editor delle schede
        return in_reportlab(testo)
    # **testo** scritto nelle schede prima dell'editor esce in grassetto
    testo = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escape(testo), flags=re.S)
    # 10⁻⁹/h del PFH: l'esponente negativo non c'è in tutti i caratteri
    return testo.replace("\n", "<br/>").replace("10⁻⁹", "10<super>-9</super>")


# ---------------------------------------------------------------------------
# Documento PDF
# ---------------------------------------------------------------------------


# Margini stretti per far stare più contenuto in ogni pagina.
MARGINE = 1.5 * cm
LARGHEZZA = A4[0] - 2 * MARGINE
MARGINE_VERTICALE = 1.2 * cm
ALTEZZA = A4[1] - 2 * MARGINE_VERTICALE


# Le tabelle possono spezzare una riga tra due pagine (splitInRow): un testo lungo (note,
# considerazioni) non deve superare l'altezza della pagina.
class Pdf:
    """Documento A4 con intestazione BOZZA (se serve) e numero di pagina."""

    def __init__(self, titolo, bozza="", pagina="Pagina", orizzontale=False):
        normale, grassetto, _ = _carattere_registrato()
        self.formato = landscape(A4) if orizzontale else A4
        self.larghezza = self.formato[0] - 2 * MARGINE
        self.altezza = self.formato[1] - 2 * MARGINE_VERTICALE
        self.titolo, self.bozza, self.pagina = titolo, bozza, pagina
        self.grassetto = grassetto
        base = ParagraphStyle("base", fontName=normale, fontSize=9, leading=11, spaceAfter=2)
        self.stili = {
            "base": base,
            "cella": ParagraphStyle("cella", parent=base, leading=10.8, spaceAfter=0),
            "cella_piccola": ParagraphStyle("cella_piccola", parent=base, fontSize=7.5, leading=9, spaceAfter=0),
            "etichetta": ParagraphStyle("etichetta", parent=base, fontName=grassetto, leading=10.8,
                                        textColor=colors.HexColor("#4A5563"), spaceAfter=0),
            "testata": ParagraphStyle("testata", parent=base, fontName=grassetto, fontSize=10.5, leading=12.5, spaceAfter=0),
            "sottotitolo_misure": ParagraphStyle("sottotitolo_misure", parent=base, fontName=grassetto, leading=10.8,
                                                 textColor=colors.HexColor("#4A5563"), spaceBefore=1, spaceAfter=0,
                                                 keepWithNext=1),
            "sezione": ParagraphStyle("sezione", parent=base, fontName=grassetto, fontSize=9.5, leading=11.5,
                                      textColor=colors.HexColor("#2F4A6D"), spaceBefore=4, spaceAfter=1, keepWithNext=1),
            "titolo": ParagraphStyle("titolo", parent=base, fontName=grassetto, fontSize=15, leading=18, spaceAfter=6),
            "titolo_centro": ParagraphStyle("titolo_centro", parent=base, fontName=grassetto, fontSize=15, leading=18, alignment=TA_CENTER, spaceAfter=4),
            "centro": ParagraphStyle("centro", parent=base, alignment=TA_CENTER),
            "centro_html": ParagraphStyle("centro_html", parent=base, alignment=TA_CENTER, textColor=colors.HexColor("#4A5563")),
            "copertina": ParagraphStyle("copertina", parent=base, fontName=grassetto, fontSize=24, leading=30,
                                        alignment=TA_CENTER, textColor=colors.HexColor("#2F4A6D"), spaceAfter=6),
            1: ParagraphStyle("h1", parent=base, fontName=grassetto, fontSize=11.5, leading=14, spaceBefore=6, spaceAfter=3, keepWithNext=1),
            2: ParagraphStyle("h2", parent=base, fontName=grassetto, fontSize=10.5, leading=13, spaceBefore=5, spaceAfter=2, keepWithNext=1),
            3: ParagraphStyle("h3", parent=base, fontName=grassetto, fontSize=9.5, leading=11.5, spaceBefore=5, spaceAfter=2,
                              keepWithNext=1),
        }
        self.storia = []

    def p(self, testo, stile="base"):
        self.storia.append(Paragraph(_pulito(testo), self.stili[stile]))

    def titolo_documento(self, testo, centrato=False):
        self.p(testo, "titolo_centro" if centrato else "titolo")

    def titoletto(self, testo, livello=1):
        self.p(testo, livello)

    def grassetto_testo(self, testo, coda=""):
        self.storia.append(Paragraph(f"<b>{_pulito(testo)}</b>{_pulito(coda)}", self.stili["base"]))

    def coppia(self, etichetta, valore):
        self.storia.append(Paragraph(f"<b>{_pulito(etichetta)}:</b> {_pulito(valore or '–')}", self.stili["base"]))

    def elenco_html(self, voci):
        voci = [v for v in voci if v]
        if voci:
            self.storia.append(
                ListFlowable(
                    [ListItem(Paragraph(v, self.stili["cella"]), leftIndent=12) for v in voci],
                    bulletType="bullet", start="•", leftIndent=12, bulletFontSize=6,
                )
            )

    def elenco(self, voci):
        voci = [v for v in voci if v]
        if voci:
            self.storia.append(
                ListFlowable(
                    [ListItem(Paragraph(_pulito(v), self.stili["cella"]), leftIndent=12) for v in voci],
                    bulletType="bullet", start="•", leftIndent=12, bulletFontSize=6,
                )
            )

    def nuova_pagina(self):
        self.storia.append(PageBreak())

    def p_html(self, html, stile="base"):
        """Paragrafo con marcatura già pronta (le parti variabili vanno passate da _pulito)."""
        self.storia.append(Paragraph(html, self.stili[stile]))

    def testata(self, testo, a_destra="", sfondo="#DDE4EE", stile="testata"):
        """Fascia a tutta larghezza: titolo a sinistra, codice a destra."""
        destra = ParagraphStyle("destra", parent=self.stili[stile], alignment=TA_RIGHT)
        larghezza = self.larghezza
        tabella = Table(
            [[Paragraph(_pulito(testo), self.stili[stile]), Paragraph(_pulito(a_destra), destra)]],
            colWidths=[larghezza - 3 * cm, 3 * cm],
        )
        stile_tabella = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]
        if sfondo:
            stile_tabella += [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(sfondo)),
                ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor("#5F6B7A")),
            ]
        else:
            stile_tabella.append(("LEFTPADDING", (0, 0), (0, -1), 0))
        tabella.setStyle(TableStyle(stile_tabella))
        self.storia.append(tabella)
        self.spazio(0.5)

    def dettagli(self, righe):
        """Etichetta su una riga e valore a tutta larghezza sotto; una linea sottile separa le voci.
        Le righe senza valore non compaiono."""
        dati, stile = [], [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]
        for etichetta, valore in righe:
            if not valore:
                continue
            riga = len(dati)
            dati.append([Paragraph(_pulito(etichetta) + ":", self.stili["etichetta"])])
            dati.append([Paragraph(_pulito(valore), self.stili["cella"])])
            stile += [
                ("TOPPADDING", (0, riga), (0, riga), 2 if riga else 0), ("BOTTOMPADDING", (0, riga), (0, riga), 0),
                ("TOPPADDING", (0, riga + 1), (0, riga + 1), 0), ("BOTTOMPADDING", (0, riga + 1), (0, riga + 1), 2),
            ]
        if not dati:
            return
        # linea sotto ogni valore tranne l'ultimo (le etichette restano attaccate al loro valore)
        stile += [("LINEBELOW", (0, r), (0, r), 0.25, colors.HexColor("#D5DAE1")) for r in range(1, len(dati) - 1, 2)]
        tabella = Table(dati, colWidths=[self.larghezza], hAlign="LEFT", splitInRow=1)
        tabella.setStyle(TableStyle(stile))
        self.storia.append(tabella)
        self.spazio(1)

    def riquadro(self, testo, colore="#F3F4F6"):
        tabella = Table([[Paragraph(_pulito(testo), self.stili["cella"])]], colWidths=[self.larghezza], splitInRow=1)
        tabella.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(colore)),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA3AE")),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        self.storia.append(tabella)
        self.spazio(1)

    def spazio(self, altezza=4):
        self.storia.append(Spacer(1, altezza * mm))

    def tabella(self, intestazioni, righe, larghezze=None, sfondi=None, bordo=True, piccola=False):
        """Tabella con celle a capo automatico. sfondi: {(colonna, riga): colore}, riga 0 = intestazione.
        piccola: carattere ridotto, per i registri con molte colonne."""
        cella = self.stili["cella_piccola" if piccola else "cella"]
        dati = []
        if intestazioni:
            dati.append([Paragraph(f"<b>{_pulito(t)}</b>", cella) for t in intestazioni])
        dati += [
            [v if isinstance(v, Paragraph) else Paragraph(_pulito("" if v is None else v), cella) for v in riga]
            for riga in righe
        ]
        larghezza_utile = self.larghezza
        if larghezze:
            totale = sum(larghezze)
            larghezze = [larghezza_utile * l / totale for l in larghezze]
        tabella = Table(dati, colWidths=larghezze, repeatRows=1 if intestazioni else 0, hAlign="LEFT", splitInRow=1)
        stile = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
        if bordo:
            stile.append(("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA3AE")))
        if intestazioni:
            stile.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF0F3")))
        for (colonna, riga), colore in (sfondi or {}).items():
            stile.append(("BACKGROUND", (colonna, riga), (colonna, riga), colors.HexColor(colore)))
        tabella.setStyle(TableStyle(stile))
        self.storia.append(tabella)
        self.spazio(1)
        return tabella

    def insieme(self, *contenuti, prima=()):
        """Tiene sulla stessa pagina gli elementi `prima` e quelli aggiunti da `contenuti` (funzioni senza
        argomenti). Un blocco più alto di mezza pagina prosegue sulla pagina seguente: si va a capo solo
        se in fondo alla pagina resta poco spazio, così il titolo non resta solo e non si lasciano pagine vuote."""
        inizio = len(self.storia)
        for aggiungi in contenuti:
            aggiungi()
        blocco = list(prima) + self.storia[inizio:]
        del self.storia[inizio:]
        altezza = _listWrapOn(blocco, self.larghezza, Canvas(io.BytesIO()))[1]
        if altezza <= self.altezza / 2:
            self.storia.append(KeepTogether(blocco))
            return
        self.storia.append(CondPageBreak(4 * cm))
        for f in blocco:
            f.keepWithNext = 0
        self.storia.extend(blocco)

    def _pagina(self, canvas, doc):
        canvas.saveState()
        larghezza, altezza = self.formato
        if self.bozza:
            canvas.setFont(self.grassetto, 10)
            canvas.setFillColor(colors.HexColor("#B3261E"))
            canvas.drawCentredString(larghezza / 2, altezza - 0.8 * cm, self.bozza)
        canvas.setFont(_carattere_registrato()[0], 7.5)
        canvas.setFillColor(colors.HexColor("#5F6B7A"))
        canvas.drawString(MARGINE, 0.7 * cm, self.titolo)
        canvas.drawRightString(larghezza - MARGINE, 0.7 * cm, f"{self.pagina} {doc.page}")
        canvas.restoreState()

    def salva(self):
        buffer = io.BytesIO()
        documento = SimpleDocTemplate(
            buffer, pagesize=self.formato, leftMargin=MARGINE, rightMargin=MARGINE, topMargin=MARGINE_VERTICALE, bottomMargin=MARGINE_VERTICALE,
            title=self.titolo, author="Cosmap – Analisi dei rischi",
        )
        documento.build(self.storia, onFirstPage=self._pagina, onLaterPages=self._pagina)
        return buffer.getvalue()


def _testo_bozza(revisione, lingua="it"):
    return "" if revisione.stato == Revisione.Stato.APPROVATA else TESTI[lingua]["bozza"]


def _schede_attive(revisione):
    return list(
        revisione.schede.exclude(decisione=SchedaAnalisi.Decisione.SCARTATA)
        .select_related("modulo", "requisito", "revisione__metodo")
        .prefetch_related(
            "misure__norma", "misure__soluzione__norme", "pericoli__norme", "requisito__norme", "norme_escluse",
            "condizioni", "norme", "soggetti", "allegati",
        )
    )


def _nome(utente):
    if not utente:
        return "–"
    return utente.get_full_name() or utente.username


def _soluzioni():
    """Soluzioni di protezione con parole chiave, lette una volta per documento (vedi Stima.origini_norme)."""
    return list(SoluzioneProtezione.objects.exclude(parole_chiave="").prefetch_related("norme"))


def norme_generali(revisione):
    """Norme che valgono per tutta l'analisi: quelle sempre applicate (es. EN ISO 12100) e quelle di tipo C
    scelte nei dati della macchina."""
    macchina = revisione.analisi.macchina
    norme = {n.pk: n for n in Norma.objects.filter(sempre_applicata=True)}
    norme.update({n.pk: n for n in macchina.norme_tipo_c.all()})
    return sorted(norme.values(), key=lambda n: (n.tipo, n.codice))


def norme_applicate(revisione):
    """Norme dell'analisi: generali, delle schede attive, dei loro pericoli e delle soluzioni scelte nelle misure.
    Restituisce (armonizzate, altre), ordinate per codice."""
    norme = {n.pk: n for n in norme_generali(revisione)}
    soluzioni = _soluzioni()
    for scheda in _schede_attive(revisione):
        for norma in [*scheda.norme.all(), *scheda.norme_collegate(soluzioni)]:
            norme[norma.pk] = norma
        for misura in scheda.misure.all():
            if misura.norma:
                norme[misura.norma.pk] = misura.norma
    # Funzioni di sicurezza calcolate e validate con la validazione approvata
    validazione = getattr(revisione, "validazione", None)
    if validazione and validazione.stato == ValidazioneSicurezza.Stato.APPROVATA:
        for norma in Norma.objects.filter(codice__in=("EN ISO 13849-1", "EN ISO 13849-2")):
            norme[norma.pk] = norma
    # Equipaggiamento elettrico verificato: tutte le verifiche elettriche della revisione approvate
    verifiche = list(revisione.verifiche_elettriche.values_list("stato", flat=True))
    if verifiche and all(stato == VerificaElettrica.Stato.APPROVATA for stato in verifiche):
        for norma in Norma.objects.filter(codice="EN 60204-1"):
            norme[norma.pk] = norma
    ordinate = sorted(norme.values(), key=lambda n: n.codice)
    return [n for n in ordinate if n.armonizzata], [n for n in ordinate if not n.armonizzata]


def _edizione(norma):
    edizione = norma.edizione_vigente or norma.edizione_citata
    return f"{norma.codice}:{edizione}" if edizione else norma.codice


# ---------------------------------------------------------------------------
# Dichiarazione UE di conformità
# ---------------------------------------------------------------------------


def dichiarazione(revisione, lingua="it"):
    t = TESTI[lingua]
    fabbricante = Fabbricante.corrente()
    macchina = revisione.analisi.macchina
    commessa = macchina.commessa
    doc = Pdf(f"{t['titolo']} {commessa.numero}/{revisione.numero}", _testo_bozza(revisione, lingua), t["pagina"])

    doc.titolo_documento(t["titolo"], centrato=True)
    doc.p(t["sottotitolo"], "centro")
    doc.p(f"{t['numero']} {commessa.numero}/{revisione.numero}", "centro")

    doc.titoletto(f"1. {t['fabbricante']}", 2)
    if fabbricante:
        doc.p(fabbricante.ragione_sociale)
        doc.p(fabbricante.indirizzo)
        if fabbricante.partita_iva:
            doc.coppia(t["piva"], fabbricante.partita_iva)
    else:
        doc.p("Dati del fabbricante non impostati.")

    doc.titoletto(f"2. {t['fascicolo']}", 2)
    if fabbricante and fabbricante.persona_fascicolo:
        doc.p(fabbricante.persona_fascicolo)
        doc.p(fabbricante.indirizzo_persona_fascicolo or fabbricante.indirizzo)
    else:
        doc.p("–")

    doc.titoletto(f"3. {t['oggetto']}", 2)
    doc.coppia(t["denominazione"], macchina.denominazione)
    doc.coppia(t["funzione"], macchina.funzione)
    doc.coppia(t["modello"], macchina.modello)
    doc.coppia(t["matricola"], macchina.matricola)
    doc.coppia(t["anno"], str(macchina.anno_costruzione or ""))

    doc.titoletto("4.", 2)
    doc.p(t["responsabilita"])

    legislazioni = list(macchina.altre_legislazioni.all())
    doc.titoletto("5.", 2)
    doc.p(t["conforme"] + (t["conforme_altre"] if legislazioni else "."))
    doc.elenco(
        f"{legge.codice} – {legge.titolo_en if lingua == 'en' and legge.titolo_en else legge.titolo}"
        for legge in legislazioni
    )

    armonizzate, altre = norme_applicate(revisione)
    doc.titoletto(f"6. {t['norme_arm']}", 2)
    if armonizzate:
        doc.elenco(_edizione(norma) for norma in armonizzate)
    else:
        doc.p("–")
    if altre:
        doc.grassetto_testo(t["norme_altre"])
        doc.elenco(_edizione(norma) for norma in altre)

    if macchina.organismo_notificato.strip():
        doc.titoletto(f"7. {t['organismo']}", 2)
        doc.p(macchina.organismo_notificato)

    luogo = fabbricante.luogo if fabbricante else ""
    data = f"{timezone.localtime(revisione.approvata_il):%d/%m/%Y}" if revisione.approvata_il else "____________"
    firmatario = f"{fabbricante.firmatario}, {fabbricante.qualifica_firmatario}" if fabbricante else ""
    doc.insieme(
        lambda: doc.spazio(6),
        lambda: doc.p(f"{t['firmato']}: {fabbricante.ragione_sociale if fabbricante else ''}"),
        lambda: doc.tabella(
            None,
            [[t["luogo_data"], f"{luogo}, {data}"], [t["nome_qualifica"], firmatario], [t["firma"], "\n\n______________________________"]],
            [5, 12],
            bordo=False,
        ),
    )
    return doc.salva()


# ---------------------------------------------------------------------------
# Valutazione dei rischi
# ---------------------------------------------------------------------------


FATTORI = ("Se", "Fr", "Pr", "Av")


def _valore(descrizioni, fattore, valore):
    if valore is None:
        return "–"
    descrizione = descrizioni.get((fattore, valore))
    return f"{valore} – {descrizione}" if descrizione else str(valore)


def _cella_valore(doc, descrizioni, fattore, valore):
    """Numero in grassetto, descrizione più piccola in grigio."""
    if valore is None:
        return Paragraph("–", doc.stili["cella"])
    descrizione = descrizioni.get((fattore, valore))
    coda = f' <font color="#5F6B7A">– {_pulito(descrizione)}</font>' if descrizione else ""
    return Paragraph(f"<b>{valore}</b>{coda}", doc.stili["cella"])


NOMI_FATTORI = {
    "Se": "Gravità",
    "Fr": "Frequenza di esposizione",
    "Pr": "Probabilità dell'evento",
    "Av": "Possibilità di evitare",
}
TIPI_MISURA = [
    ("PROG", "Progettazione intrinsecamente sicura"),
    ("PROT", "Protezione e misure complementari (ripari e dispositivi di protezione)"),
    ("INFO", "Informazioni per l'uso"),
    ("DACL", "Da classificare"),
]


def _tabella_stima(doc, scheda, descrizioni, quale):
    righe = [
        [f"{fattore} – {NOMI_FATTORI[fattore]}", _cella_valore(doc, descrizioni, fattore, getattr(scheda, f"{fattore.lower()}_{quale}"))]
        for fattore in FATTORI
    ]
    esito = getattr(scheda, f"esito_{quale}")
    righe.append([
        f"Cl = Fr + Pr + Av = {_valore({}, '', getattr(scheda, f'cl_{quale}'))}",
        Paragraph(f"<b>Esito:</b> {_pulito(ESITI_TESTO.get(esito, '–'))}", doc.stili["cella"]),
    ])
    sfondi = {(1, len(righe) - 1): ESITI_COLORE[esito]} if esito else {}
    doc.tabella(None, righe, [5.6, 12.4], sfondi)


def _riepilogo(doc, schede):
    """Una riga per scheda con gli esiti colorati: la panoramica dell'analisi."""
    righe, sfondi = [], {}
    for indice, s in enumerate(schede, start=1):
        esiti = [s.esito_iniziale, s.esito_finale]
        righe.append([
            f"{s.requisito.codice} {s.requisito.titolo}", s.zona_pericolosa or s.zona_impianto,
            *(ESITI_TESTO.get(e, "–") for e in esiti), s.codice or "–",
        ])
        sfondi.update({(colonna, indice): ESITI_COLORE[e] for colonna, e in enumerate(esiti, start=2) if e})
    doc.tabella(["Requisito", "Zona pericolosa", "Esito iniziale", "Esito finale", "Scheda"], righe, [5.1, 5.1, 3, 3, 1.8], sfondi)


# Sezioni della scheda in sequenza EN ISO 12100, come nella scheda a video.
SEZIONI_SCHEDA = [
    "1. IDENTIFICAZIONE SCHEDA",
    "2. IDENTIFICAZIONE DEL PERICOLO (RESS 1.1.1 a)",
    "3. IDENTIFICAZIONE DELLA ZONA PERICOLOSA (RESS 1.1.1 b)",
    "4. IDENTIFICAZIONE DEI SOGGETTI ESPOSTI (RESS 1.1.1 c, d)",
    "5. STIMA INIZIALE DEL RISCHIO (RESS 1.1.1 e)",
    "6. RIDUZIONE DEL RISCHIO (RESS 1.1.1 f, g)",
    "7. STIMA FINALE DEL RISCHIO (RESS 1.1.1 e)",
    "8. VALUTAZIONE DEL RISCHIO RESIDUO",
    "9. IMMAGINI ALLEGATE",
]


def _sezione(doc, numero, righe=(), considerazioni="", contenuto=None, considerazioni_prima=False, prima=()):
    """Titolo della sezione, voci, contenuto aggiuntivo e considerazioni (in fondo, o all'inizio come nella
    scheda a video); la sezione vuota non compare."""
    righe = [(etichetta, valore) for etichetta, valore in righe if valore]
    if not (righe or considerazioni or contenuto):
        return
    parti = [lambda: doc.p(SEZIONI_SCHEDA[numero - 1], "sezione")]
    if considerazioni and considerazioni_prima:
        parti.append(lambda: doc.dettagli([("Considerazioni", considerazioni)]))
    if righe:
        parti.append(lambda: doc.dettagli(righe))
    if contenuto:
        parti.append(contenuto)
    if considerazioni and not considerazioni_prima:
        parti.append(lambda: doc.dettagli([("Considerazioni", considerazioni)]))
    doc.insieme(*parti, prima=prima)


def _misure(doc, misure):
    for tipo, titolo in TIPI_MISURA:
        del_tipo = [m for m in misure if m.tipo == tipo]
        if del_tipo:
            doc.p(titolo, "sottotitolo_misure")
            doc.elenco_html(_pulito(m.testo) for m in del_tipo)


def _elenco_norme(norme):
    """Una norma per riga con codice, edizione e titolo (sezioni 1 e 6 della scheda)."""
    return "\n".join(
        f"{_edizione(n)} – {n.titolo}" if n.titolo else _edizione(n) for n in sorted(set(norme), key=lambda n: n.codice)
    )


def _scheda(doc, s, descrizioni):
    doc.testata(f"{s.requisito.codice} {s.requisito.titolo}", s.codice)
    testata = doc.storia[-2:]
    del doc.storia[-2:]
    # La testata non resta sola in fondo alla pagina: va con la sezione 1.
    dettagli = [("Modulo", str(s.modulo))]
    if s.stampa_note_requisito and s.requisito.descrizione:
        dettagli.append((f"Requisito {s.requisito.codice} – testo del Regolamento", s.requisito.descrizione))
    # Norme della scheda, dei pericoli analizzati e delle soluzioni scelte nelle misure, in un unico elenco
    norme = [*s.norme.all(), *s.norme_collegate()]
    dettagli += [("Note", s.note), ("Norme", _elenco_norme(norme))]
    _sezione(doc, 1, dettagli, prima=testata)
    _sezione(doc, 2, [("Pericoli", "\n".join(f"{p.codice} {p.descrizione}" for p in s.pericoli.all()))],
             s.considerazioni_pericoli, considerazioni_prima=True)
    _sezione(doc, 3, [
        ("Zona dell'impianto", s.zona_impianto),
        ("Zona pericolosa", s.zona_pericolosa),
        ("Considerazioni", s.considerazioni_limiti),
        ("Condizioni operative", ", ".join(c.nome for c in s.condizioni.all())),
    ])
    _sezione(doc, 4, [("Soggetti esposti", ", ".join(f.nome for f in s.soggetti.all()))], s.considerazioni_soggetti,
             considerazioni_prima=True)
    _sezione(doc, 5, considerazioni=s.considerazioni_stima_iniziale,
             contenuto=(lambda: _tabella_stima(doc, s, descrizioni, "iniziale")) if s.ha_stima_iniziale else None)
    misure = list(s.misure.all())
    norme_misure = _elenco_norme(m.norma for m in misure if m.norma)

    def riduzione():
        _misure(doc, misure)
        doc.dettagli([("Norme", norme_misure)])

    _sezione(doc, 6, considerazioni=s.considerazioni_riduzione, considerazioni_prima=True,
             contenuto=riduzione if misure else None)
    _sezione(doc, 7, considerazioni=s.considerazioni_stima_finale,
             contenuto=(lambda: _tabella_stima(doc, s, descrizioni, "finale")) if s.ha_stima_finale else None)
    if s.testo_istruzioni:
        da_segnalare = s.esito_finale and s.esito_finale != Esito.OK
        _sezione(doc, 8, contenuto=lambda: doc.riquadro(
            s.testo_istruzioni,
            ESITI_COLORE[Esito.SUGGERITE] if da_segnalare else "#F3F4F6",
        ))
    allegati = list(s.allegati.all())
    if allegati:
        _sezione(doc, 9, contenuto=lambda: _allegati(doc, allegati))
    doc.spazio(4)


def _immagine(allegato, larghezza=LARGHEZZA, altezza=12 * cm):
    """Immagine allegata ridotta nel riquadro dato, o None se il file manca o non si legge."""
    try:
        percorso = allegato.file.path
        w, h = ImageReader(percorso).getSize()
    except Exception:
        return None
    scala = min(larghezza / w, altezza / h, 1)
    return Image(percorso, width=w * scala, height=h * scala)


ALLINEAMENTI = {"SX": ("LEFT", TA_LEFT), "CENTRO": ("CENTER", TA_CENTER), "DX": ("RIGHT", TA_RIGHT)}


def _immagine_con_testo(doc, allegato):
    """Immagine nella posizione scelta (sinistra, centro, destra) con il suo testo sopra, sotto o di fianco."""
    di_fianco = allegato.testo and allegato.posizione_testo in ("SX", "DX")
    # Al massimo 2/3 della larghezza utile, così la posizione a sinistra, al centro o a destra si vede.
    immagine = _immagine(allegato, larghezza=LARGHEZZA * (0.55 if di_fianco else 2 / 3), altezza=9 * cm)
    if immagine is None:
        return [Paragraph(_pulito(f"Immagine non disponibile: {allegato.nome_file}"), doc.stili["base"])]
    allinea, allinea_testo = ALLINEAMENTI.get(allegato.allineamento, ALLINEAMENTI["CENTRO"])
    if not allegato.testo:
        immagine.hAlign = allinea
        return [immagine]
    if di_fianco:
        # Immagine e testo affiancati su tutta la larghezza: il testo occupa lo spazio che resta.
        testo = Paragraph(_pulito(allegato.testo), doc.stili["cella"])
        larghezza_immagine = immagine.drawWidth + 8
        celle = [immagine, testo] if allegato.posizione_testo == "DX" else [testo, immagine]
        colonne = [larghezza_immagine, LARGHEZZA - larghezza_immagine]
        if allegato.posizione_testo == "SX":
            colonne.reverse()
        tabella = Table([celle], colWidths=colonne)
        tabella.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        return [tabella]
    immagine.hAlign = allinea
    stile = ParagraphStyle(f"testo_allegato_{allinea}", parent=doc.stili["base"], alignment=allinea_testo)
    testo = Paragraph(_pulito(allegato.testo), stile)
    return [testo, Spacer(1, 1.5 * mm), immagine] if allegato.posizione_testo == "SOPRA" else [immagine, Spacer(1, 1.5 * mm), testo]


def _allegati(doc, allegati):
    """Sezione 9: immagini stampate nella scheda con il loro testo; i PDF sono in appendice al documento."""
    for allegato in allegati:
        if allegato.e_immagine:
            doc.storia.append(KeepTogether(_immagine_con_testo(doc, allegato)))
            doc.spazio(4)
        else:
            nome = _pulito(allegato.nome_file)
            testo = f" – {_pulito(allegato.testo)}" if allegato.testo else ""
            doc.p_html(f"PDF allegato in appendice: {nome}{testo}")


def _con_pdf_allegati(contenuto, schede):
    """Aggiunge in fondo al documento le pagine dei PDF allegati alle schede, nell'ordine delle schede."""
    pdf = [a for s in schede for a in s.allegati.all() if not a.e_immagine]
    if not pdf:
        return contenuto
    from pypdf import PdfReader, PdfWriter

    scrittore = PdfWriter(clone_from=PdfReader(io.BytesIO(contenuto)))
    for allegato in pdf:
        try:
            with allegato.file.open("rb") as f:
                scrittore.append(PdfReader(io.BytesIO(f.read())))
        except Exception:  # file mancante o non leggibile: resta solo la riga nella scheda
            continue
    uscita = io.BytesIO()
    scrittore.write(uscita)
    return uscita.getvalue()


def _logo(fabbricante, larghezza=7 * cm, altezza=3.5 * cm):
    """Logo del fabbricante ridotto nel riquadro dato, o None se non c'è o non si legge."""
    if not (fabbricante and fabbricante.logo):
        return None
    try:
        percorso = fabbricante.logo.path
        w, h = ImageReader(percorso).getSize()
    except Exception:  # file mancante o non leggibile: si stampa il nome
        return None
    scala = min(larghezza / w, altezza / h)
    return Image(percorso, width=w * scala, height=h * scala, hAlign="LEFT")


def _intestazione(doc, revisione):
    """Pagina di intestazione: logo, titolo, dati della commessa e firme della revisione."""
    macchina = revisione.analisi.macchina
    commessa = macchina.commessa
    fabbricante = Fabbricante.objects.first()
    logo = _logo(fabbricante)
    if logo:
        doc.storia.append(logo)
    elif fabbricante:
        doc.p(fabbricante.ragione_sociale, "titolo")
    doc.spazio(30)
    doc.p("VALUTAZIONE DEI RISCHI", "copertina")
    doc.p(f"{REGOLAMENTO} relativo alle macchine – Allegato III", "centro")
    doc.spazio(14)
    doc.tabella(None, [
        ["Commessa", commessa.numero],
        ["Cliente", str(commessa.cliente)],
        ["Macchina", macchina.denominazione],
        ["Modello", macchina.modello or "–"],
        ["Matricola", macchina.matricola or "–"],
        ["Anno di costruzione", str(macchina.anno_costruzione or "–")],
        ["Revisione", f"{revisione.numero} – {revisione.motivo}"],
    ], [5, 13])
    doc.spazio(10)
    doc.tabella(
        ["", "Nome", "Data"],
        [
            ["Compilata", _nome(revisione.compilata_da), f"{revisione.creata_il:%d/%m/%Y}"],
            ["Verificata", _nome(revisione.verificata_da), f"{revisione.verificata_il:%d/%m/%Y}" if revisione.verificata_il else "–"],
            ["Approvata", _nome(revisione.approvata_da), f"{revisione.approvata_il:%d/%m/%Y}" if revisione.approvata_il else "–"],
        ],
        [4, 7, 4],
    )
    if fabbricante:
        doc.spazio(20)
        doc.p_html(f"<b>{_pulito(fabbricante.ragione_sociale)}</b><br/>{_pulito(fabbricante.indirizzo)}", "centro_html")


def valutazione(revisione):
    macchina = revisione.analisi.macchina
    commessa = macchina.commessa
    metodo = revisione.metodo
    doc = Pdf(f"Valutazione dei rischi – commessa {commessa.numero} rev. {revisione.numero}", _testo_bozza(revisione))

    _intestazione(doc, revisione)
    doc.nuova_pagina()

    # Capitoli di testo modificabili da Libreria e utenti (Definizioni, Principi generali…)
    for capitolo in CapitoloValutazione.objects.filter(attivo=True):
        doc.titoletto(capitolo.titolo)
        for paragrafo in _pulito(capitolo.testo).split("<br/><br/>"):
            if paragrafo.strip():
                doc.p_html(paragrafo)

    doc.titoletto("Soggetti")
    doc.p(
        "Operatori (RESS 1.1.1 d): persone incaricate di installare, far funzionare, regolare, pulire, "
        "riparare o spostare la macchina. Persone esposte (RESS 1.1.1 c): chiunque si trovi interamente "
        "o in parte in una zona pericolosa."
    )
    descrizioni_figure = macchina.descrizioni_figure()
    figure_usate = {f for s in _schede_attive(revisione) for f in s.soggetti.all()}
    figure_usate |= {f.figura for f in macchina.figure.select_related("figura")}
    if figure_usate:
        doc.tabella(
            ["Tipo", "Figura", "Chi è su questa macchina"],
            [
                [f.get_tipo_display(), f.nome, descrizioni_figure.get(f.pk) or f.descrizione]
                for f in sorted(figure_usate, key=lambda f: (f.ordine, f.nome))
            ],
            [4.6, 4, 9.4],
        )
    else:
        doc.p("Soggetti non ancora indicati.")

    doc.titoletto("Metodo di stima")
    doc.p(
        f"{metodo.versione}. Rischio (RESS 1.1.1 e) stimato con la gravità Se da 1 a 4 e la classe "
        "Cl = Fr + Pr + Av (frequenza di esposizione, probabilità dell'evento pericoloso, possibilità di "
        "evitare il danno). L'esito si legge nella matrice."
    )
    fasce = list(metodo.fasce.all())
    righe, sfondi = [], {}
    for indice, se in enumerate((4, 3, 2, 1), start=1):
        esiti = [metodo.esito(se, f.cl_min) for f in fasce]
        righe.append([f"Se {se}"] + [ESITI_TESTO.get(e, "–") for e in esiti])
        sfondi.update({(colonna, indice): ESITI_COLORE[e] for colonna, e in enumerate(esiti, start=1) if e})
    doc.tabella(["Gravità"] + [f"Cl {f.cl_min}-{f.cl_max}" for f in fasce], righe, None, sfondi)

    descrizioni = metodo.descrizioni()
    if descrizioni:
        doc.p("Valori dei fattori:")
        doc.tabella(
            ["Fattore", "Valore", "Descrizione"],
            [[f, v, descrizioni[(f, v)]] for f in FATTORI for v in sorted({v for (ff, v) in descrizioni if ff == f}, reverse=True)],
            [2, 2, 13],
        )

    doc.titoletto("Norme di riferimento dell'analisi")
    generali = norme_generali(revisione)
    if generali:
        doc.tabella(
            ["Tipo", "Norma", "Titolo"],
            [[n.get_tipo_display(), _edizione(n), n.titolo] for n in generali],
            [2, 5, 10],
        )
        doc.p("Le norme specifiche di ogni rischio sono indicate nella sezione 1 della scheda.")
    else:
        doc.p("Nessuna norma generale indicata: le norme sono indicate nella sezione 1 di ogni scheda.")

    doc.titoletto("Requisiti non applicabili")
    non_applicabili = revisione.applicabilita.filter(applicabile=False).select_related("requisito")
    if non_applicabili:
        doc.tabella(
            ["Requisito", "Motivazione"],
            [[f"{a.requisito.codice} {a.requisito.titolo}", a.motivazione] for a in non_applicabili],
            [6, 11],
        )
    else:
        doc.p("Tutti i requisiti sono considerati applicabili.")

    schede = _schede_attive(revisione)
    doc.titoletto("Riepilogo delle schede")
    _riepilogo(doc, schede)

    # Ogni scheda inizia su una pagina nuova; il titolo del modulo sta sopra la sua prima scheda.
    for modulo, gruppo in groupby(schede, key=lambda s: s.modulo):
        for numero, s in enumerate(gruppo):
            doc.nuova_pagina()
            if not numero:
                doc.titoletto(f"Modulo: {modulo.nome}" + (f" ({modulo.sigla})" if modulo.sigla else ""))
            _scheda(doc, s, descrizioni)

    scartate = revisione.schede.filter(decisione=SchedaAnalisi.Decisione.SCARTATA).select_related("requisito")
    if scartate:
        doc.nuova_pagina()
        doc.titoletto("Schede proposte e scartate")
        doc.tabella(
            ["Requisito", "Motivazione", "Scheda"],
            [[f"{s.requisito.codice} {s.requisito.titolo}", s.motivazione, s.codice] for s in scartate],
            [6, 8.5, 2.5],
        )
    return _con_pdf_allegati(doc.salva(), schede)


# ---------------------------------------------------------------------------
# Elenco dei rischi residui
# ---------------------------------------------------------------------------


def rischi_residui(revisione):
    macchina = revisione.analisi.macchina
    doc = Pdf(f"Rischi residui – commessa {macchina.commessa.numero} rev. {revisione.numero}", _testo_bozza(revisione))
    doc.titolo_documento("Rischi residui e informazioni per le istruzioni")
    doc.p(
        f"Commessa {macchina.commessa.numero} · {macchina.denominazione} {macchina.modello}".strip()
        + f" · matricola {macchina.matricola or '–'} · valutazione dei rischi rev. {revisione.numero}"
    )
    schede = [s for s in _schede_attive(revisione) if s.testo_istruzioni.strip()]
    if not schede:
        doc.p("Nessun rischio residuo indicato nelle schede.")
    for modulo, gruppo in groupby(schede, key=lambda s: s.modulo):
        doc.titoletto(modulo.nome)
        for s in gruppo:
            esito = f"  [{ESITI_TESTO[s.esito_finale]}]" if s.esito_finale and s.esito_finale != Esito.OK else ""
            doc.insieme(
                lambda s=s, esito=esito: doc.testata(
                    f"{s.requisito.codice} {s.requisito.titolo}{esito}", s.codice, sfondo="", stile=3
                ),
                lambda s=s: doc.p(s.testo_istruzioni),
            )
    return doc.salva()


# ---------------------------------------------------------------------------
# Relazione sulle funzioni di sicurezza (EN ISO 13849-1, EN ISO 13849-2)
# ---------------------------------------------------------------------------

RUOLI = {"rilevamento": "Rilevamento", "comunicazione": "Comunicazione", "logica": "Logica", "attuazione": "Attuazione"}
COLORI_RUOLO = {"rilevamento": "#0B6BCB", "comunicazione": "#7A5AF8", "logica": "#1A7F4B", "attuazione": "#C2410C"}
ESITI_PROVA = {"ok": "OK", "ko": "Non OK", "na": "Non applicabile"}
COLORI_PROVA = {"ok": "#E6F4E7", "ko": "#FDE8E6"}
METODI = {"arch": "Architettura designata", "pfh": "PFH da certificato"}


def _numero(valore, decimali=1):
    if valore is None:
        return "–"
    return f"{valore:,.{decimali}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _data_testo(testo):
    """'2026-10-17' → '17/10/2026'; il resto com'è."""
    if testo and re.fullmatch(r"\d{4}-\d{2}-\d{2}", testo):
        anno, mese, giorno = testo.split("-")
        return f"{giorno}/{mese}/{anno}"
    return testo or ""


GRIGIO_SCHEMA = "#5F6B7A"


def _righe_testo(testo, larghezza, dimensione, massimo):
    """Testo a capo nella larghezza data (al massimo `massimo` righe, l'ultima chiusa da … se non basta)."""
    normale = _carattere_registrato()[0]
    righe = simpleSplit(testo or "–", normale, dimensione, larghezza) or ["–"]
    if len(righe) > massimo:
        righe = righe[:massimo]
        while righe[-1] and pdfmetrics.stringWidth(righe[-1] + "…", normale, dimensione) > larghezza:
            righe[-1] = righe[-1][:-1]
        righe[-1] += "…"
    return righe


def _blocco_schema(disegno, x, y, larghezza, altezza, blocco):
    normale = _carattere_registrato()[0]
    colore = colors.HexColor(COLORI_RUOLO.get(blocco["ruolo"], GRIGIO_SCHEMA))
    disegno.add(Rect(x, y, larghezza, altezza, rx=3, ry=3, fillColor=colors.HexColor("#F7F8FA"),
                     strokeColor=colors.HexColor(GRIGIO_SCHEMA), strokeWidth=0.6,
                     strokeDashArray=[3, 2] if blocco["comune"] else None))
    disegno.add(Rect(x, y, 1.6 * mm, altezza, fillColor=colore, strokeColor=None))
    # nome a capo (fino a tre righe) sopra il ruolo
    for k, riga in enumerate(_righe_testo(blocco["nome"], larghezza - 3.6 * mm, 7, 3)):
        disegno.add(String(x + 2.6 * mm, y + altezza - 3.6 * mm - k * 2.9 * mm, riga, fontName=normale, fontSize=7))
    disegno.add(String(x + 2.6 * mm, y + 1.8 * mm, RUOLI.get(blocco["ruolo"], blocco["ruolo"]).upper(),
                       fontName=normale, fontSize=5.8, fillColor=colore))


def _freccia_schema(disegno, x1, x2, y):
    """Freccia orizzontale da x1 a x2 (punta su x2)."""
    grigio = colors.HexColor(GRIGIO_SCHEMA)
    disegno.add(Line(x1, y, x2 - 1 * mm, y, strokeColor=grigio, strokeWidth=0.8))
    disegno.add(Polygon([x2 - 1 * mm, y + 1.2 * mm, x2, y, x2 - 1 * mm, y - 1.2 * mm], fillColor=grigio, strokeColor=None))


def _albero_schema(r):
    """Albero delle confluenze dal risultato del calcolo (calcola.js): nodo = {blocchi, rami}, percorso = {nome,
    blocchi}. Senza confluenza, un percorso per riga con tutti i sottosistemi in serie."""
    if r.get("albero"):
        return r["albero"]
    if r.get("confluenza"):  # forma di prima: un solo livello di confluenza
        return {"blocchi": r["confluenza"]["comuni"], "rami": r["confluenza"]["propri"]}
    return {"blocchi": [], "rami": r["schema"]}


def _schema_a_blocchi(albero):
    """Schema a blocchi come nella pagina: ogni percorso ha la sua riga con i blocchi propri e confluisce nei
    sottosistemi comuni (bordo tratteggiato), disegnati una volta sola; con blocchi comuni solo ad alcuni
    percorsi le confluenze sono più d'una. I nomi di percorsi e blocchi vanno a capo."""
    normale = _carattere_registrato()[0]
    grigio = colors.HexColor(GRIGIO_SCHEMA)
    foglie = []

    def visita(nodo, profondita):
        if "rami" not in nodo:
            foglie.append(nodo)
            return {}
        livelli = {profondita: len(nodo["blocchi"])}
        for ramo in nodo["rami"]:
            for d, n in visita(ramo, profondita + 1).items():
                livelli[d] = max(livelli.get(d, 0), n)
        return livelli

    livelli = visita(albero, 1)
    colonne = sorted((d for d, n in livelli.items() if n), reverse=True)  # da sinistra: confluenze più a monte
    etichetta = 2.8 * cm if any(f["nome"] for f in foglie) else 0
    propri = max((len(f["blocchi"]) for f in foglie), default=0) or (0 if colonne else 1)
    freccia = 0.6 * cm
    blocchi = propri + sum(livelli[d] for d in colonne)
    frecce = max(propri - 1, 0) + sum(livelli[d] for d in colonne)  # una per ogni passaggio, bus compresi
    larghezza = min(3.6 * cm, (LARGHEZZA - etichetta - 0.2 * cm - freccia * frecce) / max(blocchi, 1))
    altezza_blocco, passo = 1.35 * cm, 1.75 * cm
    disegno = Drawing(LARGHEZZA, passo * len(foglie))
    # ascissa del bus (linea di confluenza) di ogni livello
    x = etichetta + 0.2 * cm + propri * larghezza + max(propri - 1, 0) * freccia
    bus = {}
    for d in colonne:
        bus[d] = x + freccia / 2
        x += freccia + livelli[d] * larghezza + (livelli[d] - 1) * freccia

    def serie(elenco, x, y):
        for j, blocco in enumerate(elenco):
            _blocco_schema(disegno, x, y - altezza_blocco / 2, larghezza, altezza_blocco, blocco)
            x += larghezza
            if j < len(elenco) - 1:
                _freccia_schema(disegno, x + 1 * mm, x + freccia - 0.5 * mm, y)
                x += freccia
        return x

    riga = iter(range(len(foglie)))

    def disegna(nodo, profondita):
        """Disegna il nodo e restituisce (ordinata dell'uscita, ascissa dove finisce)."""
        if "rami" not in nodo:
            y = passo * (len(foglie) - 1 - next(riga)) + passo / 2
            if nodo["nome"]:
                testo = _righe_testo(nodo["nome"], etichetta - 0.3 * cm, 8, 3)
                for k, t in enumerate(testo):
                    disegno.add(String(0, y + (len(testo) - 1) * 1.6 * mm - 1.1 * mm - k * 3.2 * mm, t, fontName=normale, fontSize=8))
            return y, serie(nodo["blocchi"], etichetta + 0.2 * cm, y)
        uscite = [disegna(ramo, profondita + 1) for ramo in nodo["rami"]]
        if not nodo["blocchi"]:
            return None, None
        b = bus[profondita]
        for y, fine in uscite:
            if y is not None:
                disegno.add(Line(fine + 1 * mm, y, b, y, strokeColor=grigio, strokeWidth=0.8))
        centri = [y for y, _ in uscite if y is not None]
        if len(centri) > 1:
            disegno.add(Line(b, min(centri), b, max(centri), strokeColor=grigio, strokeWidth=0.8))
        y = (min(centri) + max(centri)) / 2
        _freccia_schema(disegno, b, b + freccia / 2 - 0.5 * mm, y)
        return y, serie(nodo["blocchi"], b + freccia / 2, y)

    disegna(albero, 1)
    return disegno


def _grafo_rischio(s, f, p):
    """Grafo del rischio (EN ISO 13849-1, fig. A.1) con il percorso della funzione evidenziato, come nella pagina."""
    from .grafico_pl import COLORI, FOGLIE

    normale, grassetto = _carattere_registrato()[0], _carattere_registrato()[1]
    scelta = (s or "") + ((f or "") + ((p or "") if f else "") if s else "")
    riga_h, sopra = 0.55 * cm, 0.5 * cm
    altezza = sopra + 8 * riga_h + 0.2 * cm
    x0, xs, xf, xp, xl = 0.3 * cm, 2.6 * cm, 5.1 * cm, 7.6 * cm, 8.6 * cm
    disegno = Drawing(LARGHEZZA, altezza)
    blu, grigio = colors.HexColor("#1F4E79"), colors.HexColor("#9AA3AE")

    def y(primo, quanti):  # dall'alto: centro di un gruppo di foglie
        return altezza - sopra - (primo + (quanti - 1) / 2 + 0.5) * riga_h

    def ramo(chiave, x1, y1, x2, y2, etichetta):
        attivo = scelta.startswith(chiave)
        tratto = dict(strokeColor=blu if attivo else grigio, strokeWidth=2.2 if attivo else 0.8)
        disegno.add(Line(x1, y1, x1 + 0.3 * cm, y2, **tratto))
        disegno.add(Line(x1 + 0.3 * cm, y2, x2, y2, **tratto))
        disegno.add(String(x1 + 0.4 * cm, y2 + 1.2 * mm, etichetta, fontName=grassetto if attivo else normale, fontSize=7.5))

    disegno.add(String(xl, altezza - 0.35 * cm, "PLr", fontName=normale, fontSize=7.5, fillColor=colors.HexColor(GRIGIO_SCHEMA)))
    for i, sv in enumerate(("S1", "S2")):
        ys = y(i * 4, 4)
        ramo(sv, x0, y(0, 8), xs, ys, sv)
        for j, fv in enumerate(("F1", "F2")):
            yf = y(i * 4 + j * 2, 2)
            ramo(sv + fv, xs, ys, xf, yf, fv)
            for k, pv in enumerate(("P1", "P2")):
                n = i * 4 + j * 2 + k
                yp = y(n, 1)
                chiave = sv + fv + pv
                ramo(chiave, xf, yf, xp, yp, pv)
                attivo = scelta == chiave
                disegno.add(Line(xp, yp, xl, yp, strokeColor=blu if attivo else grigio, strokeWidth=2.2 if attivo else 0.8))
                lettera = FOGLIE[n]
                disegno.add(Rect(xl, yp - 0.22 * cm, 0.8 * cm, 0.44 * cm, rx=2, ry=2, fillColor=colors.HexColor(COLORI[lettera]),
                                 strokeColor=blu if attivo else None, strokeWidth=1.6))
                disegno.add(String(xl + 0.4 * cm, yp - 0.1 * cm, lettera, fontName=grassetto, fontSize=8.5, textAnchor="middle"))
    disegno.add(Circle(x0, y(0, 8), 1.2 * mm, fillColor=colors.black, strokeColor=None))
    legenda = ["S1 lesione lieve · S2 lesione grave", "F1 esposizione rara o breve · F2 frequente o lunga",
               "P1 evitabile · P2 difficilmente evitabile"]
    for n, testo in enumerate(legenda):
        disegno.add(String(xl + 1.4 * cm, y(2 + n, 1), testo, fontName=normale, fontSize=7.5, fillColor=colors.HexColor(GRIGIO_SCHEMA)))
    return disegno


def _firme_validazione(doc, validazione, revisione):
    data = lambda d: f"{d:%d/%m/%Y}" if d else ""
    doc.tabella(
        ["", "Nome", "Data", "Firma"],
        [
            ["Compilata", _nome(validazione.compilata_da) if validazione.compilata_da else "", data(validazione.compilata_il), ""],
            ["Verificata", _nome(validazione.verificata_da) if validazione.verificata_da else "", data(validazione.verificata_il), ""],
            ["Approvata", _nome(validazione.approvata_da) if validazione.approvata_da else "", data(validazione.approvata_il), ""],
        ],
        [3, 6, 3, 5],
    )
    if revisione.approvata_da:
        doc.p(
            f"Funzioni, PLr e calcolo del PL fanno parte della valutazione dei rischi rev. {revisione.numero}, "
            f"approvata da {_nome(revisione.approvata_da)} il {revisione.approvata_il:%d/%m/%Y}."
        )
    else:
        doc.p(f"Funzioni, PLr e calcolo del PL: valutazione dei rischi rev. {revisione.numero}, non ancora approvata.")


def _capitolo_funzione(doc, numero, riga, articoli):
    funzione, r = riga.funzione, riga.risultato
    valutazione = getattr(funzione, "valutazione", None)
    doc.titoletto(f"{numero}. {funzione.nome}")
    misure = [f"{m.scheda.codice or 'scheda'}: {m.testo}" for m in funzione.misure.all()]
    doc.dettagli([
        ("Descrizione", funzione.descrizione),
        ("Misure di protezione delle schede", "\n".join(misure) or "Funzione non collegata a una scheda (inserita a mano)."),
    ])

    doc.titoletto(f"{numero}.1 PLr dal grafo del rischio (EN ISO 13849-1, allegato A)", 2)
    doc.tabella(None, [
        ["Gravità della lesione", funzione.get_s_display() or "–"],
        ["Frequenza e/o durata dell'esposizione", funzione.get_f_display() or "–"],
        ["Possibilità di evitare il pericolo", funzione.get_p_display() or "–"],
        ["PLr", funzione.plr or "–"],
    ], [6, 11])
    doc.storia.append(_grafo_rischio(funzione.s, funzione.f, funzione.p))
    doc.p("Grafo del rischio (EN ISO 13849-1, figura A.1): il percorso evidenziato porta al PLr della funzione.")

    doc.titoletto(f"{numero}.2 Schema a blocchi", 2)
    if r["schema"] and any(riga_s["blocchi"] for riga_s in r["schema"]):
        albero = _albero_schema(r)
        doc.storia.append(_schema_a_blocchi(albero))
        doc.spazio(1)
        doc.p("Ogni riga è un percorso; i sottosistemi sono in serie. "
              + ("I percorsi confluiscono nei sottosistemi comuni (bordo tratteggiato), disegnati una volta sola."
                 if albero["blocchi"] or any("rami" in ramo for ramo in albero["rami"])
                 else "Bordo tratteggiato: sottosistema comune a più percorsi."))
    else:
        doc.p("Schema a blocchi non compilato.")

    doc.titoletto(f"{numero}.3 Sottosistemi e componenti", 2)
    if r["sottosistemi"]:
        doc.tabella(
            ["Sottosistema", "Ruolo", "Metodo", "Cat.", "MTTFd [anni]", "DCavg [%]", "CCF", "PFH [10⁻⁹/h]", "PL"],
            [[
                ss["nome"] + (f" ({ss['percorso']})" if ss["percorso"] else ""), RUOLI.get(ss["ruolo"], ss["ruolo"]),
                METODI.get(ss["metodo"], ss["metodo"]), ss["categoria"] if ss["metodo"] == "arch" else "–",
                _numero(ss["mttfd"]) if ss["metodo"] == "arch" else "–", _numero(ss["dcavg"]) if ss["metodo"] == "arch" else "–",
                ss["ccf"] if ss["ccf"] is not None else "–",
                _numero(ss["pfh"], 2) + (" (a mano)" if ss["pfhManuale"] else ""), ss["pl"] or "–",
            ] for ss in r["sottosistemi"]],
            [3.8, 2.3, 2.6, 1.2, 1.8, 1.6, 1.1, 2.2, 1],
        )
        componenti = []
        for ss in r["sottosistemi"]:
            for c in ss["componenti"]:
                a = articoli.get(c["articoloId"])
                componenti.append([
                    ss["nome"], f"{a.codice} – {a.descrizione}" if a else f"{c['articoloId']} (non in libreria)",
                    a.produttore if a else "", c["qty"], c["canale"] if ss["metodo"] == "arch" else "–",
                    f"{_numero(c['dc'], 0)} %" if ss["metodo"] == "arch" and c["dc"] is not None else "–",
                ])
        if componenti:
            doc.tabella(["Sottosistema", "Articolo", "Produttore", "Q.tà", "Canale", "DC"], componenti, [3.5, 6.6, 2.8, 1.1, 1.7, 1.3])
        fonti_k1 = sorted({ss["fonteK1"] for ss in r["sottosistemi"] if ss["fonteK1"]})
        if fonti_k1:
            doc.p("PFH dei sottosistemi in architettura designata: " + "; ".join(fonti_k1) + ".")
    else:
        doc.p("Nessun sottosistema.")

    doc.titoletto(f"{numero}.4 Verifica PL ≥ PLr", 2)
    if len(r["percorsi"]) > 1:
        doc.tabella(
            ["Percorso", "PFH [10⁻⁹/h]", "PL"],
            [[p["nome"] + (" (peggiore)" if p["peggiore"] else ""), _numero(p["pfh"], 2), p["pl"] or "–"] for p in r["percorsi"]],
            [8, 4, 2],
        )
    pl = r["pl"] if r["pl"] in ("a", "b", "c", "d", "e") else None
    if r["ok"]:
        testo, colore = f"PL {pl} ≥ PLr {r['plr']}: requisito soddisfatto (PFH {_numero(r['pfh'], 2)} · 10⁻⁹/h).", "#E6F4E7"
    else:
        testo = f"PL {pl or 'non calcolabile'}, PLr {r['plr'] or '–'}: requisito non dimostrato."
        colore = "#FDE8E6"
    doc.riquadro(testo, colore)
    doc.elenco([f"Errore: {e}" for e in r["errori"]] + [f"Avviso: {a}" for a in r["avvisi"]])
    if valutazione and valutazione.calcolata_il:
        doc.p(f"Calcolo salvato il {valutazione.calcolata_il:%d/%m/%Y}; mission time {valutazione.dettaglio.get('missionTime') or calcolo.MISSION_TIME} anni. "
              "Risultati ricalcolati per questa relazione con lo stesso motore della pagina.")

    doc.titoletto(f"{numero}.5 Validazione (EN ISO 13849-2)", 2)
    dati = funzione.prove.dati if hasattr(funzione, "prove") else {}
    righe, sfondi = [], {}
    for indice, p in enumerate(riga.prove, start=1):
        esito = p.get("esito", "")
        righe.append([indice, p.get("testo") or "–", p.get("atteso", ""), ESITI_PROVA.get(esito, ""), p.get("note", "")])
        if esito in COLORI_PROVA:
            sfondi[(3, indice)] = COLORI_PROVA[esito]
    doc.tabella(["N.", "Prova", "Risultato atteso", "Esito", "Note"], righe, [0.8, 6, 5, 2, 3.5], sfondi)
    esito = "Funzione validata: tutte le prove applicabili sono OK." if riga.riepilogo["completa"] else (
        f"Validazione non completa: {riga.riepilogo['aperte']} prove da eseguire, {riga.riepilogo['ko']} non OK."
    )
    doc.p(esito)
    doc.spazio(2)
    doc.tabella(None, [[
        f"Prove eseguite da: {dati.get('esecutore') or ''}\n\n", f"Data: {_data_testo(dati.get('data'))}", "Firma:",
    ]], [7, 4, 6])


def relazione_funzioni(revisione):
    from .servizi import quadro_validazione

    quadro = quadro_validazione(revisione)
    if quadro["sistematiche"] is None:
        raise calcolo.CalcoloNonRiuscito("Node non è installato sul server.")
    validazione, righe = quadro["validazione"], quadro["righe"]
    macchina = revisione.analisi.macchina
    commessa = macchina.commessa
    approvata = validazione.stato == ValidazioneSicurezza.Stato.APPROVATA
    doc = Pdf(
        f"Relazione funzioni di sicurezza – commessa {commessa.numero} rev. {revisione.numero}",
        "" if approvata else "BOZZA – validazione non approvata, documento non valido",
    )

    fabbricante = Fabbricante.objects.first()
    logo = _logo(fabbricante)
    if logo:
        doc.storia.append(logo)
    elif fabbricante:
        doc.p(fabbricante.ragione_sociale, "titolo")
    doc.spazio(24)
    doc.p("RELAZIONE SULLE FUNZIONI DI SICUREZZA", "copertina")
    doc.p("EN ISO 13849-1 (progettazione e calcolo del PL) – EN ISO 13849-2 (validazione)", "centro")
    doc.spazio(12)
    doc.tabella(None, [
        ["Commessa", commessa.numero],
        ["Cliente", str(commessa.cliente)],
        ["Macchina", macchina.denominazione],
        ["Modello", macchina.modello or "–"],
        ["Matricola", macchina.matricola or "–"],
        ["Valutazione dei rischi", f"rev. {revisione.numero} – {revisione.get_stato_display().lower()}"],
    ], [5, 13])
    doc.spazio(8)
    _firme_validazione(doc, validazione, revisione)
    doc.nuova_pagina()

    doc.titoletto("Metodo")
    doc.p(
        "Per ogni funzione di sicurezza: PLr dal grafo del rischio (EN ISO 13849-1, allegato A); schema a blocchi dei "
        "sottosistemi in serie, con i percorsi alternativi; PL di ogni sottosistema in architettura designata (MTTFd, "
        "allegati C e D; DCavg, allegato E; CCF, allegato F; PFH dalla tabella K.1) oppure dal PFH del certificato del "
        "costruttore; PL della funzione dal percorso peggiore e confronto con il PLr. La validazione (EN ISO 13849-2) "
        "comprende le prove sulla macchina e le misure contro i guasti sistematici (EN ISO 13849-1, allegato G)."
    )
    doc.titoletto("Riepilogo delle funzioni")
    righe_riepilogo, sfondi = [], {}
    for indice, riga in enumerate(righe, start=1):
        f, r = riga.funzione, riga.risultato
        pl = r["pl"] if r["pl"] in ("a", "b", "c", "d", "e") else "–"
        misure = ", ".join(sorted({m.scheda.codice for m in f.misure.all() if m.scheda.codice})) or "–"
        validata = "Validata" if riga.riepilogo["completa"] else "Non completa"
        righe_riepilogo.append([indice, f.nome, misure, f.plr or "–", pl, _numero(r["pfh"], 2), "Sì" if r["ok"] else "No", validata])
        sfondi[(6, indice)] = "#E6F4E7" if r["ok"] else "#FDE8E6"
        sfondi[(7, indice)] = "#E6F4E7" if riga.riepilogo["completa"] else "#FFF6D6"
    if righe_riepilogo:
        doc.tabella(["N.", "Funzione", "Schede", "PLr", "PL", "PFH [10⁻⁹/h]", "PL ≥ PLr", "Validazione"],
                    righe_riepilogo, [0.8, 5.5, 2.5, 1, 1, 2.2, 1.6, 2.4], sfondi)
    else:
        doc.p("La revisione non ha funzioni di sicurezza.")

    chiavi = {c["articoloId"] for riga in righe for ss in riga.risultato["sottosistemi"] for c in ss["componenti"]}
    articoli = {a.chiave: a for a in ArticoloSicurezza.objects.filter(chiave__in=chiavi - {None, ""})}
    for indice, riga in enumerate(righe, start=1):
        doc.nuova_pagina()
        _capitolo_funzione(doc, indice, riga, articoli)

    doc.nuova_pagina()
    doc.titoletto("Misure contro i guasti sistematici (EN ISO 13849-1, allegato G)")
    sis = validazione.sistematiche or {}
    esiti = sis.get("esiti") or {}
    for gruppo in quadro["sistematiche"]:
        doc.titoletto(gruppo["gruppo"], 3)
        sfondi, righe_m = {}, []
        for indice, (chiave, testo) in enumerate(gruppo["misure"], start=1):
            e = esiti.get(chiave) or {}
            righe_m.append([testo, ESITI_PROVA.get(e.get("esito", ""), ""), e.get("note", "")])
            if e.get("esito") in COLORI_PROVA:
                sfondi[(1, indice)] = COLORI_PROVA[e["esito"]]
        doc.tabella(["Misura", "Esito", "Note / riferimento"], righe_m, [9, 2.2, 5.8], sfondi)
    doc.coppia("Progetto software / versione", sis.get("swVersione"))
    doc.coppia("Firma del programma F", sis.get("swFirma"))

    doc.titoletto("Componenti e fonti dei dati")
    if articoli:
        doc.tabella(
            ["Articolo", "Produttore", "PFH [10⁻⁹/h]", "B10d", "MTTFd [anni]", "Fonte", "Verificato"],
            [[
                f"{a.codice} – {a.descrizione}", a.produttore, _numero(a.pfh, 2) if a.pfh is not None else "–",
                _numero(a.b10d, 0) if a.b10d is not None else "–", _numero(a.mttfd) if a.mttfd is not None else "–",
                a.fonte or "manca la fonte", "Sì" if a.verificato else "Da verificare",
            ] for a in sorted(articoli.values(), key=lambda a: (a.produttore, a.codice))],
            [4.6, 2.4, 1.8, 1.6, 1.8, 3.9, 2.3],
        )
    else:
        doc.p("Nessun componente scelto.")
    return doc.salva()


# ---------------------------------------------------------------------------
# Verifiche elettriche di un quadro (IEC 60204-1, cap. 18) e modulo rilievi per i tecnici
# ---------------------------------------------------------------------------


# Proporzioni delle colonne del registro cavi (A4 orizzontale); le misure hanno 1,3, l'isolamento 1,25
LARGHEZZE_CAVI = {"sigla": 1.5, "percorso": 2.4, "tipo": 2.0, "formazione": 2.0, "sezione": 1.3, "protezione": 1.9,
                  "in": 1.1, "note": 2.0, "l1pe": 1.25, "l2pe": 1.25, "l3pe": 1.25, "l1l2": 1.25, "l1l3": 1.25, "l2l3": 1.25}


def _dati_quadro(verifica):
    macchina = verifica.revisione.analisi.macchina
    dati = verifica.dati or {}
    return macchina, dati


def _valore_prova(p):
    if p.get("misurato"):
        return f"{p['misurato']} {p.get('unita') or ''}".strip()
    if p.get("dalRegistro"):
        return f"{p['dalRegistro']} {p.get('unita') or ''} (registro)".strip()
    return ""


def verifiche_elettriche(verifica):
    """Documento da firmare delle verifiche elettriche di un quadro: dati, firme, prove, registro misure."""
    r = calcolo.elettriche(verifica.dati or {})
    macchina, dati = _dati_quadro(verifica)
    commessa = macchina.commessa
    approvata = verifica.stato == verifica.Stato.APPROVATA
    doc = Pdf(
        f"Verifiche elettriche – commessa {commessa.numero} – {verifica.quadro} – analisi rev. {verifica.revisione.numero}",
        "" if approvata else "BOZZA – verifica non approvata, documento non valido",
        orizzontale=True,
    )
    fabbricante = Fabbricante.objects.first()
    if fabbricante:
        doc.p(fabbricante.ragione_sociale, "etichetta")
    doc.titolo_documento("Verifiche dell'equipaggiamento elettrico")
    doc.p(f"EN 60204-1, capitolo 18 · riferimento: {r['fonte']}.")
    doc.tabella(None, [
        ["Commessa", commessa.numero, "Equipaggiamento / quadro", verifica.quadro],
        ["Cliente", str(commessa.cliente), "Tensione nominale", dati.get("tensione") or "–"],
        ["Macchina", macchina.denominazione, "Strumento", dati.get("strumento") or "–"],
        ["Modello", macchina.modello or "–", "Scadenza taratura", _data_testo(dati.get("taratura")) or "–"],
        ["Matricola", macchina.matricola or "–", "Tensione di prova isolamento", dati.get("vprova") or "–"],
    ], [3, 7, 4.5, 7])
    data = lambda d: f"{d:%d/%m/%Y}" if d else ""
    doc.tabella(
        ["", "Nome", "Data", "Firma"],
        [
            ["Compilata", _nome(verifica.compilata_da) if verifica.compilata_da else "", data(verifica.compilata_il), ""],
            ["Verificata", _nome(verifica.verificata_da) if verifica.verificata_da else "", data(verifica.verificata_il), ""],
            ["Approvata", _nome(verifica.approvata_da) if verifica.approvata_da else "", data(verifica.approvata_il), ""],
        ],
        [3, 7, 3, 8],
    )

    doc.titoletto("Prove")
    righe, sfondi = [], {}
    for indice, p in enumerate(r["prove"], start=1):
        esito = p.get("esito", "")
        righe.append([p.get("clausola") or "", p.get("testo") or "–", p.get("criterio") or "", _valore_prova(p),
                      ESITI_PROVA.get(esito, ""), p.get("note", "")])
        if esito in COLORI_PROVA:
            sfondi[(4, indice)] = COLORI_PROVA[esito]
    doc.tabella(["Rif.", "Prova", "Criterio", "Misurato", "Esito", "Note"], righe, [1.4, 7, 8, 3, 2, 4.5], sfondi)

    equi, cavi = dati.get("equipotenziali") or [], dati.get("cavi") or []
    if equi or cavi:
        doc.titoletto("Registro misure")
        if dati.get("vprova"):
            doc.p(f"Tensione di prova isolamento: {dati['vprova'].rstrip('.')}. Isolamento in MΩ, RPE e Zs in Ω.")
    if equi:
        colonne = r["colonne"]["equipotenziali"]
        doc.titoletto("Collegamenti equipotenziali (18.2.2)", 3)
        doc.tabella(["N."] + [t for _, t in colonne], [[i] + [x.get(k, "") for k, _ in colonne] for i, x in enumerate(equi, 1)],
                    [0.8, 9, 4, 2.5, 2.5, 7], piccola=True)
    if cavi:
        colonne = r["colonne"]["cavi"]
        doc.titoletto("Cavi (18.2.2, 18.2.3, 18.3)", 3)
        righe, sfondi = [], {}
        for i, (x, iso) in enumerate(zip(cavi, r["isolamento"]), start=1):
            righe.append([i] + [x.get(k, "") for k, _ in colonne] + [{"ok": "OK", "ko": "Non OK"}.get(iso, "")])
            if iso in COLORI_PROVA:
                sfondi[(len(colonne) + 1, i)] = COLORI_PROVA[iso]
        doc.tabella(["N."] + [t for _, t in colonne] + ["Isol."], righe,
                    [0.8] + [LARGHEZZE_CAVI.get(k, 1.3) for k, _ in colonne] + [1.4], sfondi, piccola=True)
    doc.spazio(2)
    doc.tabella(None, [[
        f"Prove eseguite da: {dati.get('esecutore') or ''}\n\n", f"Data: {_data_testo(dati.get('data'))}", "Firma:",
    ]], [8, 4, 8])
    return doc.salva()


def modulo_tecnici(verifica):
    """Modulo da stampare per i tecnici: dati della macchina e righe del registro con i valori da scrivere a mano.
    Non è un documento firmato dell'analisi e non si archivia."""
    r = calcolo.elettriche(verifica.dati or {})
    macchina, dati = _dati_quadro(verifica)
    doc = Pdf(f"Modulo rilievi – commessa {macchina.commessa.numero} – {verifica.quadro}", orizzontale=True)
    cella = doc.stili["cella_piccola"]
    vuoto = "______________________"

    def tabella(intestazioni, righe, larghezze, vuote):
        dati_tab = [[Paragraph(f"<b>{_pulito(t)}</b>", cella) for t in intestazioni]]
        dati_tab += [[Paragraph(_pulito(v), cella) for v in riga] for riga in righe]
        dati_tab += [[""] * len(intestazioni) for _ in range(vuote)]
        totale = sum(larghezze)
        t = Table(dati_tab, colWidths=[doc.larghezza * l / totale for l in larghezze], repeatRows=1,
                  rowHeights=[None] + [0.62 * cm] * (len(dati_tab) - 1))
        t.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#444444")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
        ]))
        doc.storia.append(t)
        doc.spazio(2)

    doc.titolo_documento("Modulo rilievi: verifiche elettriche EN 60204-1, cap. 18")
    doc.tabella(None, [
        ["Commessa", macchina.commessa.numero, "Equipaggiamento / quadro", verifica.quadro, "Data prova", ""],
        ["Macchina", macchina.denominazione, "Tensione nominale", dati.get("tensione") or vuoto, "Tensione di prova isolamento", dati.get("vprova") or vuoto],
        ["Matricola", macchina.matricola or "–", "Strumento (modello, matricola)", dati.get("strumento") or vuoto, "Scadenza taratura", _data_testo(dati.get("taratura")) or vuoto],
    ], [2.4, 5, 4.2, 5.5, 4.2, 4])
    misure = set(r["colonne"]["misure"])
    colonne = r["colonne"]["equipotenziali"]
    doc.titoletto("Collegamenti equipotenziali (18.2.2): R in Ω", 3)
    tabella(["N."] + [t for _, t in colonne],
            [[i] + ["" if k in misure else x.get(k, "") for k, _ in colonne] for i, x in enumerate(dati.get("equipotenziali") or [], 1)],
            [0.8, 9, 4, 2.5, 2.5, 7], 4)
    colonne = r["colonne"]["cavi"]
    doc.titoletto("Cavi: RPE e Zs in Ω, isolamento in MΩ", 3)
    tabella(["N."] + [t for _, t in colonne],
            [[i] + ["" if k in misure else x.get(k, "") for k, _ in colonne] for i, x in enumerate(dati.get("cavi") or [], 1)],
            [0.8] + [LARGHEZZE_CAVI.get(k, 1.3) for k, _ in colonne], 8)
    doc.titoletto("Altre prove", 3)
    tabella(["Rif.", "Prova", "Valore", "Esito", "Note"],
            [[p["clausola"], p["testo"], "", "", ""] for p in r["prove"] if p["key"] in ("tensione", "residue")],
            [1.5, 11, 3, 2.5, 6], 0)
    doc.spazio(4)
    doc.p(f"Tecnico: {vuoto}{vuoto} · Firma: {vuoto}{vuoto}")
    return doc.salva()


GENERATORI = {
    "DICHIARAZIONE": dichiarazione,
    "VALUTAZIONE": valutazione,
    "RESIDUI": rischi_residui,
    "FUNZIONI": relazione_funzioni,
}


def genera(tipo, revisione, lingua="it"):
    """Contenuto PDF del documento; solo la dichiarazione esiste anche in inglese."""
    if tipo == "DICHIARAZIONE":
        return dichiarazione(revisione, lingua)
    return GENERATORI[tipo](revisione)
