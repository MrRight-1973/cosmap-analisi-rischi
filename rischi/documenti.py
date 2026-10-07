"""Generazione dei documenti PDF di una revisione.

- Dichiarazione UE di conformità (Regolamento (UE) 2023/1230, Allegato V parte A)
- Valutazione dei rischi
- Elenco dei rischi residui per il manuale

I testi fissi della dichiarazione vanno confrontati con il testo ufficiale del
Regolamento prima dell'uso: l'applicazione struttura il documento, la
responsabilità resta di chi firma.
"""

import io
from itertools import groupby
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
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

from .models import Esito, Fabbricante, Revisione, SchedaAnalisi

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
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
]
_carattere = None


def _carattere_registrato():
    """(normale, grassetto, unicode completo) – registra il carattere una sola volta."""
    global _carattere
    if _carattere is None:
        _carattere = ("Helvetica", "Helvetica-Bold", False)
        for normale, grassetto in _CARATTERI_CANDIDATI:
            if Path(normale).exists() and Path(grassetto).exists():
                pdfmetrics.registerFont(TTFont("Testo", normale))
                pdfmetrics.registerFont(TTFont("Testo-Grassetto", grassetto))
                pdfmetrics.registerFontFamily("Testo", normal="Testo", bold="Testo-Grassetto")
                _carattere = ("Testo", "Testo-Grassetto", True)
                break
    return _carattere


def _pulito(testo):
    """Testo sicuro per i paragrafi: caratteri speciali e a capo."""
    testo = "" if testo is None else str(testo)
    if not _carattere_registrato()[2]:
        testo = testo.replace("≤", "<=").replace("≥", ">=").encode("cp1252", "replace").decode("cp1252")
    return escape(testo).replace("\n", "<br/>")


# ---------------------------------------------------------------------------
# Documento PDF
# ---------------------------------------------------------------------------


class Pdf:
    """Documento A4 con intestazione BOZZA (se serve) e numero di pagina."""

    def __init__(self, titolo, bozza="", pagina="Pagina"):
        normale, grassetto, _ = _carattere_registrato()
        self.titolo, self.bozza, self.pagina = titolo, bozza, pagina
        self.grassetto = grassetto
        base = ParagraphStyle("base", fontName=normale, fontSize=10, leading=13.5, spaceAfter=3)
        self.stili = {
            "base": base,
            "cella": ParagraphStyle("cella", parent=base, fontSize=9, leading=11.5, spaceAfter=0),
            "etichetta": ParagraphStyle("etichetta", parent=base, fontName=grassetto, fontSize=9, leading=11.5,
                                        textColor=colors.HexColor("#4A5563"), spaceAfter=0),
            "testata": ParagraphStyle("testata", parent=base, fontName=grassetto, fontSize=11, leading=14, spaceAfter=0),
            "sottotitolo_misure": ParagraphStyle("sottotitolo_misure", parent=base, fontName=grassetto, fontSize=9,
                                                 leading=12, textColor=colors.HexColor("#4A5563"), spaceBefore=3, spaceAfter=1,
                                                 keepWithNext=1),
            "sezione": ParagraphStyle("sezione", parent=base, fontName=grassetto, fontSize=8.5, leading=11,
                                      textColor=colors.HexColor("#2F4A6D"), spaceBefore=4, spaceAfter=2, keepWithNext=1),
            "titolo": ParagraphStyle("titolo", parent=base, fontName=grassetto, fontSize=17, leading=21, spaceAfter=8),
            "titolo_centro": ParagraphStyle("titolo_centro", parent=base, fontName=grassetto, fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=4),
            "centro": ParagraphStyle("centro", parent=base, alignment=TA_CENTER),
            1: ParagraphStyle("h1", parent=base, fontName=grassetto, fontSize=13, leading=16, spaceBefore=10, spaceAfter=5),
            2: ParagraphStyle("h2", parent=base, fontName=grassetto, fontSize=11.5, leading=14, spaceBefore=8, spaceAfter=4),
            3: ParagraphStyle("h3", parent=base, fontName=grassetto, fontSize=10, leading=13, spaceBefore=8, spaceAfter=3,
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
                    [ListItem(Paragraph(v, self.stili["base"]), leftIndent=12) for v in voci],
                    bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8,
                )
            )

    def elenco(self, voci):
        voci = [v for v in voci if v]
        if voci:
            self.storia.append(
                ListFlowable(
                    [ListItem(Paragraph(_pulito(v), self.stili["base"]), leftIndent=12) for v in voci],
                    bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8,
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
        larghezza = A4[0] - 4 * cm
        tabella = Table(
            [[Paragraph(_pulito(testo), self.stili[stile]), Paragraph(_pulito(a_destra), destra)]],
            colWidths=[larghezza - 3 * cm, 3 * cm],
        )
        stile_tabella = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
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
        self.spazio(1.5)

    def dettagli(self, righe):
        """Coppie etichetta/valore in due colonne; le righe senza valore non compaiono."""
        dati = [
            [Paragraph(_pulito(etichetta), self.stili["etichetta"]), Paragraph(_pulito(valore), self.stili["cella"])]
            for etichetta, valore in righe if valore
        ]
        if not dati:
            return
        tabella = Table(dati, colWidths=[4.6 * cm, A4[0] - 4 * cm - 4.6 * cm], hAlign="LEFT")
        tabella.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ("LEFTPADDING", (0, 0), (0, -1), 0),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#D5DAE1")),
        ]))
        self.storia.append(tabella)
        self.spazio(2)

    def riquadro(self, titolo, testo, colore="#F3F4F6"):
        contenuto = Paragraph(f"<b>{_pulito(titolo)}</b><br/>{_pulito(testo)}", self.stili["cella"])
        tabella = Table([[contenuto]], colWidths=[A4[0] - 4 * cm])
        tabella.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(colore)),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA3AE")),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        self.storia.append(tabella)
        self.spazio(2)

    def spazio(self, altezza=4):
        self.storia.append(Spacer(1, altezza * mm))

    def tabella(self, intestazioni, righe, larghezze=None, sfondi=None, bordo=True):
        """Tabella con celle a capo automatico. sfondi: {(colonna, riga): colore}, riga 0 = intestazione."""
        cella = self.stili["cella"]
        dati = []
        if intestazioni:
            dati.append([Paragraph(f"<b>{_pulito(t)}</b>", cella) for t in intestazioni])
        dati += [
            [v if isinstance(v, Paragraph) else Paragraph(_pulito("" if v is None else v), cella) for v in riga]
            for riga in righe
        ]
        larghezza_utile = A4[0] - 4 * cm
        if larghezze:
            totale = sum(larghezze)
            larghezze = [larghezza_utile * l / totale for l in larghezze]
        tabella = Table(dati, colWidths=larghezze, repeatRows=1 if intestazioni else 0, hAlign="LEFT")
        stile = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
        if bordo:
            stile.append(("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9AA3AE")))
        if intestazioni:
            stile.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF0F3")))
        for (colonna, riga), colore in (sfondi or {}).items():
            stile.append(("BACKGROUND", (colonna, riga), (colonna, riga), colors.HexColor(colore)))
        tabella.setStyle(TableStyle(stile))
        self.storia.append(tabella)
        self.spazio(2)
        return tabella

    def insieme(self, *contenuti):
        """Tiene sulla stessa pagina gli elementi aggiunti da `contenuti` (funzioni senza argomenti)."""
        inizio = len(self.storia)
        for aggiungi in contenuti:
            aggiungi()
        blocco = self.storia[inizio:]
        del self.storia[inizio:]
        self.storia.append(KeepTogether(blocco))

    def _pagina(self, canvas, doc):
        canvas.saveState()
        larghezza, altezza = A4
        if self.bozza:
            canvas.setFont(self.grassetto, 10)
            canvas.setFillColor(colors.HexColor("#B3261E"))
            canvas.drawCentredString(larghezza / 2, altezza - 1.1 * cm, self.bozza)
        canvas.setFont(_carattere_registrato()[0], 7.5)
        canvas.setFillColor(colors.HexColor("#5F6B7A"))
        canvas.drawString(2 * cm, 1.1 * cm, self.titolo)
        canvas.drawRightString(larghezza - 2 * cm, 1.1 * cm, f"{self.pagina} {doc.page}")
        canvas.restoreState()

    def salva(self):
        buffer = io.BytesIO()
        documento = SimpleDocTemplate(
            buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm,
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
        .prefetch_related("misure__norma", "pericoli", "condizioni", "norme", "soggetti")
    )


def _nome(utente):
    if not utente:
        return "–"
    return utente.get_full_name() or utente.username


def norme_applicate(revisione):
    """Norme citate nelle schede attive: (armonizzate, altre), ordinate per codice."""
    norme = {}
    for scheda in _schede_attive(revisione):
        for norma in scheda.norme.all():
            norme[norma.pk] = norma
        for misura in scheda.misure.all():
            if misura.norma:
                norme[misura.norma.pk] = misura.norma
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
    coda = f' <font size="7.5" color="#5F6B7A">– {_pulito(descrizione)}</font>' if descrizione else ""
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
    righe.append(["Cl = Fr + Pr + Av", _valore({}, "", getattr(scheda, f"cl_{quale}"))])
    esito = getattr(scheda, f"esito_{quale}")
    righe.append(["Esito", ESITI_TESTO.get(esito, "–")])
    sfondi = {(1, len(righe)): ESITI_COLORE[esito]} if esito else {}
    doc.tabella(["Fattore", "Valore"], righe, [4.2, 12.8], sfondi)


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
    "3. DETERMINAZIONE DEI LIMITI (RESS 1.1.1 b)",
    "4. IDENTIFICAZIONE DEI SOGGETTI ESPOSTI (RESS 1.1.1 c, d)",
    "5. STIMA INIZIALE DEL RISCHIO (RESS 1.1.1 e)",
    "6. RIDUZIONE DEL RISCHIO (RESS 1.1.1 f, g)",
    "7. STIMA FINALE DEL RISCHIO (RESS 1.1.1 e)",
    "8. VALUTAZIONE DEL RISCHIO RESIDUO (RESS 1.1.2 c)",
]


def _sezione(doc, numero, righe=(), considerazioni="", contenuto=None):
    """Titolo della sezione, voci, contenuto aggiuntivo e considerazioni; la sezione vuota non compare."""
    righe = [(etichetta, valore) for etichetta, valore in righe if valore]
    if not (righe or considerazioni or contenuto):
        return
    parti = [lambda: doc.p(SEZIONI_SCHEDA[numero - 1], "sezione")]
    if righe:
        parti.append(lambda: doc.dettagli(righe))
    if contenuto:
        parti.append(contenuto)
    if considerazioni:
        parti.append(lambda: doc.dettagli([("Considerazioni", considerazioni)]))
    doc.insieme(*parti)


def _misure(doc, misure):
    for tipo, titolo in TIPI_MISURA:
        del_tipo = [m for m in misure if m.tipo == tipo]
        if del_tipo:
            doc.p(titolo, "sottotitolo_misure")
            doc.elenco_html(
                _pulito(m.testo) + (f' <font color="#6B7280">({_pulito(m.norma)})</font>' if m.norma else "")
                for m in del_tipo
            )


def _scheda(doc, s, descrizioni):
    doc.testata(f"{s.requisito.codice} {s.requisito.titolo}", s.codice)
    _sezione(doc, 1, [("Modulo", str(s.modulo)), ("Note", s.note)])
    _sezione(doc, 2, [("Pericoli", "\n".join(f"{p.codice} {p.descrizione}" for p in s.pericoli.all()))],
             s.considerazioni_pericoli)
    _sezione(doc, 3, [
        ("Zona dell'impianto", s.zona_impianto),
        ("Zona pericolosa", s.zona_pericolosa),
        ("Condizioni operative", ", ".join(c.nome for c in s.condizioni.all())),
    ], s.considerazioni_limiti)
    _sezione(doc, 4, [("Soggetti esposti", ", ".join(f.nome for f in s.soggetti.all()))], s.considerazioni_soggetti)
    _sezione(doc, 5, considerazioni=s.considerazioni_stima_iniziale,
             contenuto=(lambda: _tabella_stima(doc, s, descrizioni, "iniziale")) if s.ha_stima_iniziale else None)
    misure = list(s.misure.all())
    _sezione(doc, 6, considerazioni=s.considerazioni_riduzione,
             contenuto=(lambda: _misure(doc, misure)) if misure else None)
    _sezione(doc, 7, considerazioni=s.considerazioni_stima_finale,
             contenuto=(lambda: _tabella_stima(doc, s, descrizioni, "finale")) if s.ha_stima_finale else None)
    if s.testo_istruzioni:
        da_segnalare = s.esito_finale and s.esito_finale != Esito.OK
        _sezione(doc, 8, contenuto=lambda: doc.riquadro(
            "Informazioni per le istruzioni / rischio residuo",
            s.testo_istruzioni,
            ESITI_COLORE[Esito.SUGGERITE] if da_segnalare else "#F3F4F6",
        ))
    doc.spazio(5)


def valutazione(revisione):
    macchina = revisione.analisi.macchina
    commessa = macchina.commessa
    metodo = revisione.metodo
    doc = Pdf(f"Valutazione dei rischi – commessa {commessa.numero} rev. {revisione.numero}", _testo_bozza(revisione))

    doc.titolo_documento("Valutazione dei rischi")
    doc.coppia("Commessa", f"{commessa.numero} – {commessa.cliente}")
    doc.coppia("Macchina", f"{macchina.denominazione} {macchina.modello}".strip())
    doc.coppia("Matricola", macchina.matricola)
    doc.coppia("Riferimento normativo", REGOLAMENTO)
    doc.coppia("Revisione", f"{revisione.numero} – {revisione.motivo}")
    doc.spazio(2)
    doc.tabella(
        ["", "Nome", "Data"],
        [
            ["Compilata", _nome(revisione.compilata_da), f"{revisione.creata_il:%d/%m/%Y}"],
            ["Verificata", _nome(revisione.verificata_da), f"{revisione.verificata_il:%d/%m/%Y}" if revisione.verificata_il else "–"],
            ["Approvata", _nome(revisione.approvata_da), f"{revisione.approvata_il:%d/%m/%Y}" if revisione.approvata_il else "–"],
        ],
        [4, 7, 4],
    )

    doc.titoletto("Definizioni (RESS 1.1.1)")
    doc.p(
        "Le schede usano le definizioni del punto 1.1.1 dell'Allegato III del Regolamento: "
        "a) pericolo; b) zona pericolosa; c) persona esposta; d) operatore; e) rischio; f) riparo; "
        "g) dispositivo di protezione; h) uso previsto; i) uso scorretto ragionevolmente prevedibile. "
        "Il riferimento alla lettera è indicato nel titolo di ogni sezione delle schede."
    )

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
            [5, 4, 8],
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

    for modulo, gruppo in groupby(schede, key=lambda s: s.modulo):
        doc.nuova_pagina()
        doc.titoletto(f"Modulo: {modulo.nome}" + (f" ({modulo.sigla})" if modulo.sigla else ""))
        for numero, s in enumerate(gruppo):
            if numero:
                doc.nuova_pagina()
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
    return doc.salva()


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


GENERATORI = {
    "DICHIARAZIONE": dichiarazione,
    "VALUTAZIONE": valutazione,
    "RESIDUI": rischi_residui,
}


def genera(tipo, revisione, lingua="it"):
    """Contenuto PDF del documento; solo la dichiarazione esiste anche in inglese."""
    if tipo == "DICHIARAZIONE":
        return dichiarazione(revisione, lingua)
    return GENERATORI[tipo](revisione)
