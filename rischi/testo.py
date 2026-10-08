"""Testi formattati delle schede.

L'editor delle schede (rischi/static/rischi/scheda.js) salva un HTML ridotto: grassetto, corsivo,
sottolineato, a capo ed elenchi. Qui lo si converte per il PDF e in testo semplice. I testi scritti
prima dell'editor (testo semplice, con **grassetto**) restano validi.
"""

import re
from html.parser import HTMLParser
from xml.sax.saxutils import escape

_TAG_EDITOR = re.compile(r"</?(b|strong|i|em|u|br|p|div|ul|ol|li|span)\b[^>]*>", re.I)
_BLOCCHI = {
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "table", "tr",
    "section", "article", "header", "footer", "address", "dl", "dt", "dd", "figure",
}
_SALTATI = {"script", "style", "head", "title", "template", "xml"}
_VUOTI = {"br", "img", "hr", "meta", "link", "input", "col", "wbr", "area", "base", "source"}


def e_formattato(testo):
    """Vero se il testo viene dall'editor (contiene i suoi tag)."""
    return bool(testo) and bool(_TAG_EDITOR.search(testo))


def _formati(tag, stile):
    stile = stile.replace(" ", "").lower()
    peso = re.search(r"font-weight:(\w+)", stile)
    grassetto = (tag in ("b", "strong") or tag[:1] == "h" and tag[1:].isdigit()) and not (
        peso and peso.group(1) in ("normal", "400", "300", "100", "200")
    )
    grassetto = grassetto or bool(peso and peso.group(1) in ("bold", "bolder", "600", "700", "800", "900"))
    corsivo = tag in ("i", "em") or "font-style:italic" in stile
    sottolineato = tag == "u" or bool(re.search(r"text-decoration[^;]*underline", stile))
    return {tag for tag, attivo in (("b", grassetto), ("i", corsivo), ("u", sottolineato)) if attivo}


class _Righe(HTMLParser):
    """Divide l'HTML in righe; ogni riga ha un eventuale punto elenco e pezzi di testo con i loro formati."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.righe = [self._riga()]
        self.aperti = []  # (tag, formati)
        self.elenchi = []  # [tag, numero]
        self.saltati = 0

    @staticmethod
    def _riga(prefisso="", livello=0):
        return {"prefisso": prefisso, "livello": livello, "pezzi": []}

    def _confine(self):
        """Inizio o fine di un blocco: va a capo solo se la riga ha già del testo (come il browser)."""
        if self.righe[-1]["pezzi"]:
            self.righe.append(self._riga())

    def handle_starttag(self, tag, attrs):
        if tag in _SALTATI or ":" in tag:
            self.saltati += 1
            return
        if tag == "br":
            self.righe.append(self._riga())
        elif tag in ("ul", "ol"):
            self._confine()
            self.elenchi.append([tag, 0])
        elif tag == "li":
            self._confine()
            if self.elenchi:
                self.elenchi[-1][1] += 1
                tipo, numero = self.elenchi[-1]
                prefisso = f"{numero}. " if tipo == "ol" else "• "
            else:
                prefisso = "• "
            self.righe[-1].update(prefisso=prefisso, livello=max(len(self.elenchi), 1))
        elif tag in _BLOCCHI:
            self._confine()
        if tag not in _VUOTI:
            self.aperti.append((tag, _formati(tag, dict(attrs).get("style") or "")))

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.righe.append(self._riga())

    def handle_endtag(self, tag):
        if tag in _SALTATI or ":" in tag:
            self.saltati = max(self.saltati - 1, 0)
            return
        if any(t == tag for t, _ in self.aperti):
            while self.aperti and self.aperti.pop()[0] != tag:
                pass
        if tag in ("ul", "ol"):
            if self.elenchi:
                self.elenchi.pop()
            self._confine()
        elif tag == "li" or tag in _BLOCCHI:
            self._confine()

    def handle_data(self, dati):
        if self.saltati:
            return
        dati = re.sub(r"[ \t\r\n]+", " ", dati)
        riga = self.righe[-1]
        if not riga["pezzi"]:
            dati = dati.lstrip(" ")
        if dati:
            formati = set().union(*(f for _, f in self.aperti))
            riga["pezzi"].append((dati, formati))

    def risultato(self):
        self.close()
        righe = self.righe
        while righe and not righe[-1]["pezzi"] and not righe[-1]["prefisso"]:
            righe.pop()
        while righe and not righe[0]["pezzi"] and not righe[0]["prefisso"]:
            righe.pop(0)
        return righe


def _righe(testo):
    lettore = _Righe()
    lettore.feed(testo)
    return lettore.risultato()


def in_reportlab(testo):
    """Marcatura per i paragrafi di reportlab: <b>, <i>, <u>, <br/>, punti elenco rientrati."""
    uscita = []
    for riga in _righe(testo):
        parti = []
        if riga["prefisso"]:
            parti.append("&nbsp;" * 4 * (riga["livello"] - 1) + escape(riga["prefisso"]))
        for dati, formati in riga["pezzi"]:
            pezzo = escape(dati)
            for tag in ("b", "i", "u"):
                if tag in formati:
                    pezzo = f"<{tag}>{pezzo}</{tag}>"
            parti.append(pezzo)
        uscita.append("".join(parti))
    return "<br/>".join(uscita)


def semplice(testo):
    """Il testo senza formattazione (per elenchi, titoli e anteprime)."""
    testo = "" if testo is None else str(testo)
    if not e_formattato(testo):
        return re.sub(r"\*\*(.+?)\*\*", r"\1", testo, flags=re.S)
    righe = []
    for riga in _righe(testo):
        rientro = "  " * (riga["livello"] - 1) if riga["prefisso"] else ""
        righe.append(rientro + riga["prefisso"] + "".join(d for d, _ in riga["pezzi"]).rstrip())
    return "\n".join(righe).replace("\xa0", " ")


def in_html(testo):
    """HTML sicuro per mostrare il testo in una pagina (sola lettura)."""
    testo = "" if testo is None else str(testo)
    if not e_formattato(testo):
        testo = escape(testo)
        return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", testo, flags=re.S).replace("\n", "<br>")
    return in_reportlab(testo).replace("<br/>", "<br>")
