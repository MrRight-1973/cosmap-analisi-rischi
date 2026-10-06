"""Importa la libreria da un file Excel (Libreria_nuova_Cosmap.xlsx o la libreria precedente).

Uso:  python manage.py importa_libreria dati/Libreria_nuova_Cosmap.xlsx

Si può rilanciare: le righe esistenti vengono aggiornate per codice.
Se il file ha il foglio "Misure", le misure si leggono da lì, una per riga con il
loro tipo; altrimenti la colonna delle misure diventa un'unica misura "Da classificare".
"""

import re

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rischi.models import (
    CellaMatrice,
    CondizioneOperativa,
    Esito,
    Figura,
    FasciaClasse,
    MetodoStima,
    MisuraModello,
    Modulo,
    Norma,
    Pericolo,
    RequisitoRESS,
    RiferimentoNormativo,
    ScalaFattore,
    SchedaModello,
    TipoMisura,
)

CONDIZIONI = [
    "Normale",
    "Regolazione / attrezzamento",
    "Programmazione",
    "Manutenzione",
    "Pulizia",
    "Sblocco anomalie",
    "Situazione di emergenza",
    "Installazione",
    "Trasporto",
    "Smantellamento",
]
ALIAS_CONDIZIONI = {"regolazione": "Regolazione / attrezzamento"}

ESITI = {"ok": Esito.OK, "suggerite": Esito.SUGGERITE, "richieste": Esito.RICHIESTE}
FATTORI = {"se": "Se", "fr": "Fr", "pr": "Pr", "av": "Av"}

RE_PERICOLO = re.compile(r"^(\d+(?:\.\d+)+)\s+(.+)$")
RE_NORMA = re.compile(
    r"\b(EN ISO/TR|ISO/TR|EN ISO|EN IEC|IEC/IEEE|IEC/TS|EN|ISO|IEC)\s+(\d[\d]*(?:-\d+)*)"
)
RE_GRUPPO_NORME = re.compile(r"Norme(?:\s+([ABC]))?\s*:")

COL = {
    "codice": 0,
    "ress": 1,
    "originale": 3,
    "zona": 4,
    "modulo": 5,
    "zona_pericolosa": 7,
    "condizioni": 8,
    "pericoli": 9,
    "se_i": 10,
    "fr_i": 11,
    "pr_i": 12,
    "av_i": 13,
    "misure": 16,
    "istruzioni": 17,
    "se_f": 18,
    "fr_f": 19,
    "pr_f": 20,
    "av_f": 21,
    "norme": 24,
    "note": 25,
    "soggetti": 26,  # facoltativa: figure separate da ";"
}


def testo(valore):
    return str(valore).strip() if valore is not None else ""


def intero(valore):
    if valore in (None, ""):
        return None
    try:
        return int(str(valore).strip())
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Importa moduli, schede modello, requisiti, norme e metodo dal file Excel della libreria."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Percorso del file .xlsx")

    @transaction.atomic
    def handle(self, *args, **opzioni):
        try:
            wb = openpyxl.load_workbook(opzioni["file"], data_only=False)
        except FileNotFoundError as e:
            raise CommandError(f"File non trovato: {opzioni['file']}") from e

        self.riferimento, _ = RiferimentoNormativo.objects.get_or_create(
            codice="UE-2023/1230", defaults={"nome": "Regolamento (UE) 2023/1230 sulle macchine"}
        )
        for i, nome in enumerate(CONDIZIONI):
            CondizioneOperativa.objects.update_or_create(nome=nome, defaults={"ordine": i})

        self.importa_metodo(wb["Metodo"])
        self.importa_requisiti(wb["RESS-Regolamento"])
        self.importa_norme(wb["Norme"])
        self.importa_moduli(wb["Moduli"])
        self.misure = self.leggi_misure(wb["Misure"]) if "Misure" in wb.sheetnames else None
        self.importa_schede(wb["Libreria"])

    # -- Metodo ---------------------------------------------------------------

    def importa_metodo(self, ws):
        righe = [list(r) for r in ws.iter_rows(values_only=True)]
        metodo, _ = MetodoStima.objects.update_or_create(
            versione="ISO/TR 14121-2 ibrido – 200741V",
            defaults={
                "descrizione": "Metodo usato nella valutazione 200741V rev. 0.0 del 22.05.2020.",
                "attivo": True,
            },
        )
        metodo.celle.all().delete()
        metodo.fasce.all().delete()
        metodo.scale.all().delete()

        limiti = next(r for r in righe if testo(r[0]).lower().startswith("limite inferiore"))
        minimi = [intero(v) for v in limiti[2:7]]
        fasce = []
        for i, cl_min in enumerate(minimi):
            cl_max = minimi[i + 1] - 1 if i + 1 < len(minimi) else 15
            fasce.append(FasciaClasse.objects.create(metodo=metodo, cl_min=cl_min, cl_max=cl_max))

        indice_limiti = righe.index(limiti)
        for r in righe[indice_limiti + 1 : indice_limiti + 5]:
            se = intero(r[1])
            for fascia, valore in zip(fasce, r[2:7]):
                CellaMatrice.objects.create(
                    metodo=metodo, se=se, fascia=fascia, esito=ESITI[testo(valore).lower()]
                )

        fattore = None
        for r in righe:
            etichetta = testo(r[0])
            chiave = etichetta[:2].lower()
            if chiave in FATTORI and "–" in etichetta:
                fattore = FATTORI[chiave]
            elif etichetta:
                fattore = None
            if fattore and intero(r[1]) is not None and testo(r[2]):
                ScalaFattore.objects.create(
                    metodo=metodo, fattore=fattore, valore=intero(r[1]), descrizione=testo(r[2])[:200]
                )
        self.stdout.write(f"Metodo: {metodo.celle.count()} celle, {metodo.scale.count()} valori di scala")

    # -- Requisiti ------------------------------------------------------------

    def importa_requisiti(self, ws):
        n = 0
        for ordine, r in enumerate(ws.iter_rows(min_row=2, values_only=True)):
            codice = testo(r[4])
            if not codice:
                continue
            direttiva = testo(r[0])
            nuovo = direttiva in ("—", "-", "")
            RequisitoRESS.objects.update_or_create(
                riferimento=self.riferimento,
                codice=codice,
                defaults={
                    "titolo": re.sub(r"\s*\(NUOVO\)\s*$", "", testo(r[1]))[:200],
                    "codice_direttiva": "" if nuovo else direttiva,
                    "nuovo": nuovo,
                    "novita": testo(r[5]),
                    "azione": testo(r[6]),
                    "ordine": ordine,
                },
            )
            n += 1
        self.stdout.write(f"Requisiti RESS: {n}")

    # -- Norme ----------------------------------------------------------------

    def importa_norme(self, ws):
        n = 0
        for r in ws.iter_rows(min_row=2, values_only=True):
            codice = testo(r[0])
            if not codice or len(codice) > 60:
                continue
            valori = {
                "edizione_citata": testo(r[1]),
                "titolo": testo(r[2])[:300],
                "edizione_vigente": testo(r[3]),
                "nota": testo(r[4]),
            }
            if len(r) > 6:
                valori["armonizzata"] = testo(r[5]).lower() in ("sì", "si", "x")
                if testo(r[6]) in Norma.Tipo.values:
                    valori["tipo"] = testo(r[6])
            Norma.objects.update_or_create(codice=codice, defaults=valori)
            n += 1
        self.stdout.write(f"Norme: {n}")

    def norme_citate(self, valore):
        """'Norme A: EN ISO 12100 Norme B: EN 60204-1 | Norme: ISO/TR 14121-2' -> [(Norma, tipo)]."""
        risultato = []
        testo_norme = testo(valore)
        gruppi = list(RE_GRUPPO_NORME.finditer(testo_norme))
        for i, gruppo in enumerate(gruppi):
            fine = gruppi[i + 1].start() if i + 1 < len(gruppi) else len(testo_norme)
            tipo = gruppo.group(1) or Norma.Tipo.ALTRO
            for prefisso, numero in RE_NORMA.findall(testo_norme[gruppo.end() : fine]):
                codice = f"{prefisso} {numero}"
                norma = Norma.objects.filter(codice=codice).first()
                if not norma:
                    norma = Norma.objects.filter(codice__startswith=f"{codice} ").first()
                if not norma:
                    norma = Norma.objects.create(codice=codice, nota="Aggiunta dall'import: completare i dati.")
                if norma.tipo == Norma.Tipo.ALTRO and tipo != Norma.Tipo.ALTRO:
                    norma.tipo = tipo
                    norma.save()
                risultato.append(norma)
        return risultato

    # -- Moduli ---------------------------------------------------------------

    def importa_moduli(self, ws):
        n = 0
        for ordine, r in enumerate(ws.iter_rows(min_row=2, values_only=True)):
            nome = testo(r[0])
            if not nome or nome.lower() == "totale":
                continue
            condizione = testo(r[2])
            Modulo.objects.update_or_create(
                nome=nome,
                defaults={
                    "descrizione": testo(r[4]),
                    "condizione": "" if condizione.lower() == "sempre" else condizione[:200],
                    "sempre_attivo": condizione.lower() == "sempre",
                    "ordine": ordine,
                    **({"sigla": testo(r[5])[:6]} if len(r) > 5 and testo(r[5]) else {}),
                },
            )
            n += 1
        self.stdout.write(f"Moduli: {n}")

    # -- Misure ---------------------------------------------------------------

    def leggi_misure(self, ws):
        """{codice scheda: [(ordine, tipo, testo, norma)]} dal foglio Misure."""
        misure = {}
        for r in ws.iter_rows(min_row=2, values_only=True):
            codice, testo_misura = testo(r[0]), testo(r[4])
            if not codice or not testo_misura:
                continue
            tipo = testo(r[2]) if testo(r[2]) in TipoMisura.values else TipoMisura.DA_CLASSIFICARE
            norma = None
            if testo(r[5]):
                norma, _ = Norma.objects.get_or_create(
                    codice=testo(r[5]), defaults={"nota": "Aggiunta dall'import: completare i dati."}
                )
            misure.setdefault(codice, []).append((intero(r[1]) or 0, tipo, testo_misura, norma))
        return misure

    # -- Schede ---------------------------------------------------------------

    def pericoli(self, valore):
        voci = []
        for riga in testo(valore).splitlines():
            riga = riga.strip()
            if not riga:
                continue
            trovato = RE_PERICOLO.match(riga)
            if trovato:
                voci.append([trovato.group(1), trovato.group(2)])
            elif voci:
                voci[-1][1] += " " + riga
        pericoli = []
        for codice, descrizione in voci:
            pericolo, _ = Pericolo.objects.get_or_create(codice=codice, defaults={"descrizione": descrizione[:300]})
            pericoli.append(pericolo)
        return pericoli

    def condizioni(self, valore):
        voci = [v.strip().rstrip(".").strip().lower() for v in re.split(r"[;\n]", testo(valore))]
        tutte = {c.nome.lower(): c for c in CondizioneOperativa.objects.all()}
        if "tutte" in voci:
            return list(tutte.values())
        risultato = []
        for voce in voci:
            nome = ALIAS_CONDIZIONI.get(voce, voce).lower()
            if nome in tutte and tutte[nome] not in risultato:
                risultato.append(tutte[nome])
        return risultato

    def soggetti(self, valore):
        figure = {f.nome.lower(): f for f in Figura.objects.all()}
        trovate, sconosciute = [], []
        for nome in re.split(r"[;\n]", testo(valore)):
            nome = nome.strip()
            if not nome:
                continue
            if nome.lower() in figure:
                trovate.append(figure[nome.lower()])
            else:
                sconosciute.append(nome)
        return trovate, sconosciute

    def importa_schede(self, ws):
        n = 0
        avvisi = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            codice = testo(r[COL["codice"]])
            if not codice:
                continue
            ress = testo(r[COL["ress"]])
            requisito = RequisitoRESS.objects.filter(
                riferimento=self.riferimento, codice_direttiva=ress
            ).first() or RequisitoRESS.objects.filter(riferimento=self.riferimento, codice=ress).first()
            if not requisito:
                avvisi.append(f"{codice}: requisito {ress} non trovato, scheda saltata")
                continue
            modulo = Modulo.objects.filter(nome=testo(r[COL["modulo"]])).first()
            if not modulo:
                avvisi.append(f"{codice}: modulo '{testo(r[COL['modulo']])}' non trovato, scheda saltata")
                continue
            scheda, _ = SchedaModello.objects.update_or_create(
                codice=codice,
                defaults={
                    "modulo": modulo,
                    "requisito": requisito,
                    "scheda_originale": testo(r[COL["originale"]]),
                    "zona_impianto": testo(r[COL["zona"]]),
                    "zona_pericolosa": testo(r[COL["zona_pericolosa"]]),
                    "se_iniziale": intero(r[COL["se_i"]]),
                    "fr_iniziale": intero(r[COL["fr_i"]]),
                    "pr_iniziale": intero(r[COL["pr_i"]]),
                    "av_iniziale": intero(r[COL["av_i"]]),
                    "se_finale": intero(r[COL["se_f"]]),
                    "fr_finale": intero(r[COL["fr_f"]]),
                    "pr_finale": intero(r[COL["pr_f"]]),
                    "av_finale": intero(r[COL["av_f"]]),
                    "testo_istruzioni": testo(r[COL["istruzioni"]]),
                    "note": testo(r[COL["note"]]),
                },
            )
            scheda.condizioni.set(self.condizioni(r[COL["condizioni"]]))
            scheda.pericoli.set(self.pericoli(r[COL["pericoli"]]))
            scheda.norme.set(self.norme_citate(r[COL["norme"]]))
            if len(r) > COL["soggetti"]:
                soggetti, sconosciuti = self.soggetti(r[COL["soggetti"]])
                scheda.soggetti.set(soggetti)
                avvisi += [f"{codice}: figura '{nome}' non trovata" for nome in sconosciuti]
            scheda.misure.all().delete()
            if self.misure is not None:
                for ordine, tipo, testo_misura, norma in self.misure.get(codice, []):
                    MisuraModello.objects.create(
                        scheda=scheda, ordine=ordine, tipo=tipo, testo=testo_misura, norma=norma
                    )
            else:
                misure = testo(r[COL["misure"]])
                if misure:
                    MisuraModello.objects.create(scheda=scheda, tipo=TipoMisura.DA_CLASSIFICARE, testo=misure)
            n += 1
        self.stdout.write(f"Schede modello: {n}, pericoli: {Pericolo.objects.count()}, norme: {Norma.objects.count()}")
        for avviso in avvisi:
            self.stdout.write(self.style.WARNING(avviso))
