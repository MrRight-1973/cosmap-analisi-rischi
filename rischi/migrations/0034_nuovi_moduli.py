"""Nuova divisione dei moduli della libreria secondo la gamma Cosmap (documento "Nuovi moduli della libreria Cosmap").

- rinomina e riordina i moduli esistenti: LUC diventa PUC (pulitura CNC), ZSM diventa ASP (aspirazione e filtrazione
  polveri), ROB diventa l'isola robotizzata;
- crea i moduli nuovi (SWC, TRC, BMF, IRT, MAN, PUS, SMS, SMC, CUT, CVT, IMC);
- sposta CMD-01 in SWC e le schede delle smerigliatrici (ROB-02, 03, 04, 07, 08) in SMC;
- le schede ZPU, doppioni di quelle ZSM, si tolgono e il modulo ZPU resta solo per le commesse già fatte (non attivo);
- aggiunge le schede nuove dei moduli nuovi (rischi/dati/schede_nuovi_moduli.json) in stato Bozza.

Le schede delle commesse già create sono copie e non cambiano. Ogni passo controlla che modulo, scheda e requisito
siano quelli attesi: se sul PC la libreria è diversa, il passo si salta.
"""

import json
from pathlib import Path

from django.db import migrations

DATI = Path(__file__).resolve().parent.parent / "dati" / "schede_nuovi_moduli.json"

# sigla attuale (o None per un modulo nuovo), sigla nuova, nome, ordine, proposto sempre, quando serve
MODULI = [
    ("GEN", "GEN", "Generale impianto", 0, True, ""),
    ("CMD", "CMD", "Comandi e funzioni di sicurezza", 1, True, ""),
    ("ELE", "ELE", "Equipaggiamento elettrico", 2, True, ""),
    ("PNE", "PNE", "Equipaggiamento pneumatico", 3, None, None),
    ("INF", "INF", "Informazioni, marcatura e istruzioni", 4, True, ""),
    (None, "SWC", "Software e connessioni", 5, True,
     "Programmi di lavoro, autoapprendimento, CAD CAM C3, teleassistenza e rete del cliente"),
    ("TAV", "TAV", "Tavola rotante a scatti", 10, None, "Base: macchine TR (TR + CNC, CPL, CPDO, CSL, CNCS…)"),
    (None, "TRC", "Tavola rotante in continuo", 11, False, "Base: macchine TRC"),
    (None, "BMF", "Bancale mobile o banco fisso", 12, False, "Base: macchine TR + BM"),
    ("ROB", "ROB", "Isola robotizzata (robot manipolatore)", 13, None,
     "Base: isole IR con robot che porta il pezzo alle unità"),
    (None, "IRT", "Robot con utensile integrato", 14, False,
     "Base: isole IRT e IRTF (elettromandrino e compensatore sul robot)"),
    (None, "MAN", "Macchina manuale a doppio gruppo", 15, False, "Base: macchine manuali CMS, CMM, CML, CMXL"),
    (None, "PUS", "Unità di pulitura semplice", 20, False, "Unità CPL, CPDO"),
    ("LUC", "PUC", "Unità di pulitura CNC", 21, None, "Unità CNC, CNC2, CNCL, CNCR"),
    (None, "SMS", "Unità di smerigliatura semplice", 22, False, "Unità CSL"),
    (None, "SMC", "Unità di smerigliatura CNC", 23, False, "Unità CNCS, RAD/REC e smerigliatrici delle isole IR"),
    (None, "CUT", "Cambio utensile automatico", 24, False, "Magazzino utensili del BM, stazione di cambio dell'IRT"),
    ("PAS", "PAS", "Impianto pasta abrasiva", 25, None, None),
    ("PAL", "PAL", "Stazione di carico a doppio pallet", 30, None, None),
    ("TRA", "TRA", "Nastro trasportatore di carico o scarico", 31, None, "Se presente nastro di carico o di scarico"),
    (None, "CVT", "Caricatore verticale o a tamburo", 32, False, "Se presente caricatore verticale o a tamburo"),
    ("CAB", "CAB", "Cabina di protezione e ripari", 40, None, None),
    ("ZSM", "ASP", "Aspirazione e filtrazione polveri", 41, None,
     "Polveri di smerigliatura e pulitura: emissioni, incendio, esplosione"),
    (None, "IMC", "Impianto combinato", 42, False, "Impianti IR + TR e linee con più macchine"),
]

# codice scheda, requisito atteso, sigla del modulo di arrivo
SPOSTAMENTI = [
    ("CMD-01", "1.1.9", "SWC"),
    ("ROB-02", "1.3.8.1", "SMC"),
    ("ROB-03", "1.3.8.2", "SMC"),
    ("ROB-04", "1.3.2", "SMC"),
    ("ROB-07", "1.5.5", "SMC"),
    ("ROB-08", "1.6.4", "SMC"),
]

# Le schede di pulitura uguali a quelle di smerigliatura (stesso requisito) diventano una sola scheda ASP.
ZPU_IN_ASP = {"1.5.13", "1.5.6", "1.5.7", "1.6.5"}
NOTA_PULITURA = (
    " Nella pulitura la polvere contiene anche residui di pasta abrasiva e fibre di cotone, più facili da incendiare."
)

# Moduli aggiunti alle macchine che hanno già il modulo da cui arrivano le schede
AGGIUNTE_MACCHINE = {"ROB": "SMC", "ZPU": "ASP", "CMD": "SWC"}


# I codici lasciati liberi da una scheda spostata non si riusano: nelle commesse già fatte indicano ancora la scheda vecchia.
def _prossimo(sigla, usati):
    prefisso = f"{sigla}-"
    numeri = [int(c[len(prefisso):]) for c in usati if c.startswith(prefisso) and c[len(prefisso):].isdigit()]
    return f"{prefisso}{max(numeri, default=0) + 1:02d}"


def applica(apps, schema_editor):
    Modulo = apps.get_model("rischi", "Modulo")
    SchedaModello = apps.get_model("rischi", "SchedaModello")
    MisuraModello = apps.get_model("rischi", "MisuraModello")
    Macchina = apps.get_model("rischi", "Macchina")
    RequisitoRESS = apps.get_model("rischi", "RequisitoRESS")
    Pericolo = apps.get_model("rischi", "Pericolo")
    Figura = apps.get_model("rischi", "Figura")
    CondizioneOperativa = apps.get_model("rischi", "CondizioneOperativa")
    usati = set(SchedaModello.objects.values_list("codice", flat=True))
    if not usati:
        return  # database nuovo, libreria ancora da importare

    # 1. Moduli: rinomina, riordina, crea; le schede di un modulo che cambia sigla prendono la sigla nuova
    moduli = {}
    for vecchia, sigla, nome, ordine, sempre, condizione in MODULI:
        modulo = Modulo.objects.filter(sigla=vecchia).first() if vecchia else None
        modulo = modulo or Modulo.objects.filter(sigla=sigla).first()
        if modulo is None:
            if vecchia:
                continue  # modulo che sul PC non c'è: si salta
            modulo = Modulo(sigla=sigla, sempre_attivo=bool(sempre))
        if not Modulo.objects.filter(nome=nome).exclude(pk=modulo.pk).exists():
            modulo.nome = nome
        sigla_prima = modulo.sigla
        modulo.sigla, modulo.ordine, modulo.attivo = sigla, ordine, True
        if sempre is not None:
            modulo.sempre_attivo = sempre
        if condizione is not None:
            modulo.condizione = condizione
        modulo.save()
        if sigla_prima and sigla_prima != sigla:
            for scheda in SchedaModello.objects.filter(modulo=modulo, codice__startswith=f"{sigla_prima}-"):
                nuovo = f"{sigla}-{scheda.codice[len(sigla_prima) + 1:]}"
                if nuovo in usati:
                    nuovo = _prossimo(sigla, usati)
                usati.add(nuovo)
                scheda.codice = nuovo
                scheda.save(update_fields=["codice"])
        moduli[sigla] = modulo

    # 2. Schede che cambiano modulo: codice nuovo con il primo numero libero
    for codice, requisito, sigla in SPOSTAMENTI:
        scheda = SchedaModello.objects.filter(codice=codice, requisito__codice=requisito).first()
        if scheda is None or sigla not in moduli:
            continue
        scheda.codice = _prossimo(sigla, usati)
        usati.add(scheda.codice)
        scheda.modulo = moduli[sigla]
        scheda.save(update_fields=["codice", "modulo"])

    # 3. ZPU dentro ASP
    zpu = Modulo.objects.filter(sigla="ZPU").first()
    if zpu and "ASP" in moduli:
        for scheda in SchedaModello.objects.filter(modulo=zpu).select_related("requisito"):
            gemella = SchedaModello.objects.filter(modulo=moduli["ASP"], requisito=scheda.requisito).first()
            if scheda.requisito.codice in ZPU_IN_ASP and gemella:
                if NOTA_PULITURA.strip() not in gemella.considerazioni_pericoli:
                    gemella.considerazioni_pericoli = (gemella.considerazioni_pericoli + NOTA_PULITURA).strip()
                    gemella.save(update_fields=["considerazioni_pericoli"])
                scheda.delete()
            else:  # scheda aggiunta a mano: passa ad ASP
                scheda.codice = _prossimo("ASP", usati)
                usati.add(scheda.codice)
                scheda.modulo = moduli["ASP"]
                scheda.save(update_fields=["codice", "modulo"])
        zpu.attivo, zpu.ordine = False, 99
        zpu.save(update_fields=["attivo", "ordine"])
        moduli["ZPU"] = zpu

    # 4. Le macchine che avevano il modulo di partenza ricevono anche quello di arrivo
    for da, a in AGGIUNTE_MACCHINE.items():
        partenza = moduli.get(da) or Modulo.objects.filter(sigla=da).first()
        if partenza and a in moduli:
            for macchina in Macchina.objects.filter(moduli=partenza):
                macchina.moduli.add(moduli[a])

    # 5. Schede nuove dei moduli nuovi, in Bozza
    for voce in json.loads(DATI.read_text(encoding="utf-8")):
        modulo = moduli.get(voce["modulo"])
        requisito = RequisitoRESS.objects.filter(codice=voce["requisito"]).first()
        if not (modulo and requisito):
            continue
        if SchedaModello.objects.filter(
            modulo=modulo, requisito=requisito, zona_pericolosa=voce["zona_pericolosa"]
        ).exists():
            continue
        codice = _prossimo(modulo.sigla, usati)
        usati.add(codice)
        iniziale, finale = voce["iniziale"], voce["finale"]
        scheda = SchedaModello.objects.create(
            codice=codice, modulo=modulo, requisito=requisito, stato="BOZZA",
            zona_impianto=voce["zona_impianto"], zona_pericolosa=voce["zona_pericolosa"],
            se_iniziale=iniziale["Se"], fr_iniziale=iniziale["Fr"], pr_iniziale=iniziale["Pr"], av_iniziale=iniziale["Av"],
            se_finale=finale["Se"], fr_finale=finale["Fr"], pr_finale=finale["Pr"], av_finale=finale["Av"],
            testo_istruzioni=voce["testo_istruzioni"], note=voce["note"], **voce["considerazioni"],
        )
        scheda.condizioni.set(CondizioneOperativa.objects.filter(nome__in=voce["condizioni"]))
        scheda.pericoli.set(Pericolo.objects.filter(codice__in=voce["pericoli"]))
        scheda.soggetti.set(Figura.objects.filter(nome__in=voce["soggetti"]))
        for ordine, misura in enumerate(voce["misure"], start=1):
            MisuraModello.objects.create(scheda=scheda, ordine=ordine, tipo=misura["tipo"], testo=misura["testo"])


class Migration(migrations.Migration):
    dependencies = [("rischi", "0033_considerazioni_schede_modello")]
    operations = [migrations.RunPython(applica, migrations.RunPython.noop)]
