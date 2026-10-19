import io
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import servizi
from .models import (
    Cliente,
    Commessa,
    Esito,
    Macchina,
    MetodoStima,
    Modulo,
    Pericolo,
    RegistroModifica,
    Revisione,
    RevisioneBloccata,
    RiferimentoNormativo,
    SchedaAnalisi,
    SchedaModello,
)
from .registro import utente_attivo

LIBRERIA = Path(settings.BASE_DIR) / "dati" / "Libreria_analisi_rischi_Cosmap.xlsx"


def crea_utente(nome, *ruoli):
    utente = User.objects.create_user(nome, password="prova-prova-123")
    for ruolo in ruoli:
        utente.groups.add(Group.objects.get_or_create(name=ruolo)[0])
    return utente


class BaseConLibreria(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("importa_libreria", str(LIBRERIA), stdout=io.StringIO())
        cls.compilatore = crea_utente("mario", servizi.COMPILATORE)
        cls.verificatore = crea_utente("lucia", servizi.VERIFICATORE)
        cls.approvatore = crea_utente("titolare", servizi.APPROVATORE)
        cls.riferimento = RiferimentoNormativo.objects.get()
        cls.cliente = Cliente.objects.create(ragione_sociale="Kohler")

    def nuova_macchina(self, numero="25-20", *moduli):
        commessa = Commessa.objects.create(
            numero=numero, cliente=self.cliente, anno=2020, riferimento=self.riferimento
        )
        macchina = Macchina.objects.create(commessa=commessa, denominazione="Impianto di prova", matricola="X1")
        macchina.moduli.set(servizi.moduli_proposti())
        if moduli:
            macchina.moduli.add(*Modulo.objects.filter(nome__startswith=moduli[0]))
        return macchina


class ImportTest(BaseConLibreria):
    def test_libreria_importata(self):
        self.assertEqual(SchedaModello.objects.count(), 78)
        self.assertEqual(self.riferimento.requisitoress_set.count(), 63)

    def test_matrice_come_foglio_metodo(self):
        metodo = MetodoStima.corrente()
        attesi = {
            4: ["SUGGERITE", "RICHIESTE", "RICHIESTE", "RICHIESTE", "RICHIESTE"],
            3: ["OK", "SUGGERITE", "RICHIESTE", "RICHIESTE", "RICHIESTE"],
            2: ["OK", "OK", "SUGGERITE", "RICHIESTE", "RICHIESTE"],
            1: ["OK", "OK", "OK", "SUGGERITE", "RICHIESTE"],
        }
        for se, esiti in attesi.items():
            self.assertEqual([metodo.esito(se, cl) for cl in (4, 6, 9, 12, 15)], esiti)

    def test_reimport_non_duplica(self):
        call_command("importa_libreria", str(LIBRERIA), stdout=io.StringIO())
        self.assertEqual(SchedaModello.objects.count(), 78)


class LibreriaNuovaTest(TestCase):
    def test_import_con_misure_classificate(self):
        import io

        from .models import MisuraModello, Norma, TipoMisura

        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        self.assertEqual(Modulo.objects.count(), 14)
        self.assertGreater(SchedaModello.objects.count(), 80)
        self.assertFalse(MisuraModello.objects.filter(tipo=TipoMisura.DA_CLASSIFICARE).exists())
        self.assertTrue(Norma.objects.get(codice="EN ISO 12100").armonizzata)
        self.assertFalse(Norma.objects.get(codice="EN IEC 62443-3-3").armonizzata)
        self.assertEqual(Norma.objects.get(codice="EN ISO 10218-2").tipo, Norma.Tipo.C)
        self.assertTrue(MisuraModello.objects.filter(scheda__codice="CAB-05", norma__codice="EN ISO 13855").exists())
        metodo = MetodoStima.corrente()
        for scheda in SchedaModello.objects.all():
            esito = metodo.esito(scheda.se_finale, scheda.cl_finale)
            self.assertNotEqual(esito, Esito.RICHIESTE, scheda.codice)
            if esito and esito != Esito.OK:
                self.assertTrue(scheda.testo_istruzioni, scheda.codice)


class CreazioneAnalisiTest(BaseConLibreria):
    def test_solo_moduli_scelti(self):
        sempre = SchedaModello.objects.filter(modulo__sempre_attivo=True).count()
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.assertEqual(analisi.revisione_corrente.schede.count(), sempre)

        tavola = "Tavola rotante"
        con_tavola = SchedaModello.objects.filter(modulo__nome__startswith=tavola).count()
        self.assertTrue(con_tavola)
        altra = servizi.crea_analisi_da_libreria(self.nuova_macchina("26-01", tavola), self.compilatore)
        self.assertEqual(altra.revisione_corrente.schede.count(), sempre + con_tavola)

    def test_copia_indipendente_dalla_libreria(self):
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        scheda = analisi.revisione_corrente.schede.filter(origine__isnull=False).first()
        modello = scheda.origine
        modello.testo_istruzioni = "Testo cambiato in libreria"
        modello.save()
        scheda.refresh_from_db()
        self.assertNotEqual(scheda.testo_istruzioni, "Testo cambiato in libreria")
        self.assertEqual(scheda.misure.count(), modello.misure.count())

    def test_solo_compilatore_crea(self):
        with self.assertRaises(PermissionDenied):
            servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.verificatore)


class FlussoTest(BaseConLibreria):
    def setUp(self):
        self.analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.rev = self.analisi.revisione_corrente

    def test_esito_calcolato(self):
        scheda = self.rev.schede.first()
        scheda.se_finale, scheda.fr_finale, scheda.pr_finale, scheda.av_finale = 3, 2, 1, 1
        self.assertEqual(scheda.cl_finale, 4)
        self.assertEqual(scheda.esito_finale, Esito.OK)

    def test_scartare_richiede_motivazione(self):
        scheda = self.rev.schede.first()
        with self.assertRaises(ValidationError):
            servizi.decidi_scheda(scheda, self.compilatore, SchedaAnalisi.Decisione.SCARTATA)
        servizi.decidi_scheda(scheda, self.compilatore, SchedaAnalisi.Decisione.SCARTATA, "Non presente")
        self.assertEqual(scheda.decisa_da, self.compilatore)

    def test_flusso_completo_e_blocco(self):
        servizi.invia_in_verifica(self.rev, self.compilatore)
        with self.assertRaises(RevisioneBloccata):
            self.rev.schede.first().save()
        with self.assertRaises(ValidationError):
            servizi.approva(self.rev, self.approvatore)  # non ancora verificata
        servizi.segna_verificata(self.rev, self.verificatore)
        servizi.approva(self.rev, self.approvatore)
        self.assertEqual(self.rev.stato, Revisione.Stato.APPROVATA)

        scheda = self.rev.schede.first()
        with self.assertRaises(RevisioneBloccata):
            scheda.pericoli.clear()
        with self.assertRaises(RevisioneBloccata):
            scheda.delete()

    def test_chi_compila_non_approva(self):
        tuttofare = crea_utente("tutto", servizi.COMPILATORE, servizi.VERIFICATORE, servizi.APPROVATORE)
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina("26-02"), tuttofare)
        rev = analisi.revisione_corrente
        servizi.invia_in_verifica(rev, tuttofare)
        servizi.segna_verificata(rev, tuttofare)
        with self.assertRaises(PermissionDenied):
            servizi.approva(rev, tuttofare)

    def test_rimanda_in_bozza(self):
        servizi.invia_in_verifica(self.rev, self.compilatore)
        with self.assertRaises(ValidationError):
            servizi.rimanda_in_bozza(self.rev, self.verificatore, "")
        servizi.rimanda_in_bozza(self.rev, self.verificatore, "Manca la stima finale")
        self.assertTrue(self.rev.modificabile)

    def test_nuova_revisione_copia_e_sostituisce(self):
        scheda = self.rev.schede.first()
        servizi.decidi_scheda(scheda, self.compilatore, SchedaAnalisi.Decisione.SCARTATA, "Non presente")
        servizi.invia_in_verifica(self.rev, self.compilatore)
        servizi.segna_verificata(self.rev, self.verificatore)
        servizi.approva(self.rev, self.approvatore)

        with self.assertRaises(ValidationError):
            servizi.nuova_revisione(self.analisi, self.compilatore, "")
        rev1 = servizi.nuova_revisione(self.analisi, self.compilatore, "Aggiunto robot")
        self.assertEqual(rev1.numero, 1)
        self.assertEqual(rev1.schede.count(), self.rev.schede.count())
        self.assertEqual(rev1.schede.filter(decisione=SchedaAnalisi.Decisione.SCARTATA).count(), 1)
        self.assertEqual(rev1.applicabilita.count(), self.rev.applicabilita.count())

        servizi.invia_in_verifica(rev1, self.compilatore)
        servizi.segna_verificata(rev1, self.verificatore)
        servizi.approva(rev1, self.approvatore)
        self.rev.refresh_from_db()
        self.assertEqual(self.rev.stato, Revisione.Stato.SOSTITUITA)

    def test_controlli_completezza(self):
        tipi = {a.tipo for a in servizi.controlli(self.rev)}
        self.assertIn("decisione", tipi)
        self.assertIn("requisito", tipi)  # es. 1.1.9, requisito nuovo senza schede

    def test_copia_da_altra_analisi(self):
        servizi.invia_in_verifica(self.rev, self.compilatore)
        servizi.segna_verificata(self.rev, self.verificatore)
        servizi.approva(self.rev, self.approvatore)
        copia = servizi.crea_analisi_da_copia(self.nuova_macchina("26-03"), self.rev, self.compilatore)
        rev = copia.revisione_corrente
        self.assertEqual(rev.schede.count(), self.rev.schede.count())
        self.assertFalse(rev.schede.exclude(decisione=SchedaAnalisi.Decisione.PROPOSTA).exists())

    def test_registro_modifiche(self):
        scheda = self.rev.schede.first()
        with utente_attivo(self.compilatore):
            scheda.se_iniziale = 4
            scheda.save()
        voce = RegistroModifica.objects.filter(oggetto_id=str(scheda.pk), azione="MODIFICA").first()
        self.assertEqual(voce.utente, self.compilatore)
        self.assertIn("se_iniziale", voce.modifiche)
        with self.assertRaises(ValidationError):
            voce.delete()


class PagineTest(BaseConLibreria):
    def test_percorso_web(self):
        self.client.force_login(self.compilatore)
        risposta = self.client.post(
            reverse("nuova_commessa"),
            {
                "numero": "27-01",
                "nuovo_cliente": "Cliente prova",
                "anno": 2027,
                "riferimento": self.riferimento.pk,
                "denominazione": "Tavola rotante",
                "tipo": "MACCHINA",
                "origine": "LIBRERIA",
                "moduli": [m.pk for m in servizi.moduli_proposti()],
            },
        )
        analisi = Commessa.objects.get(numero="27-01").macchine.get().analisi
        self.assertRedirects(risposta, reverse("analisi", args=[analisi.pk]))
        self.assertContains(self.client.get(reverse("analisi", args=[analisi.pk])), "Invia in verifica")
        self.assertContains(self.client.get(reverse("elenco_commesse")), "27-01")

        scheda = analisi.revisione_corrente.schede.first()
        self.assertEqual(self.client.get(reverse("scheda", args=[scheda.pk])).status_code, 200)
        self.client.post(reverse("conferma_scheda", args=[scheda.pk]))
        scheda.refresh_from_db()
        self.assertEqual(scheda.decisione, SchedaAnalisi.Decisione.CONFERMATA)
        self.assertEqual(
            self.client.get(reverse("applicabilita", args=[analisi.revisione_corrente.pk])).status_code, 200
        )
        # Le modifiche fatte senza utente (importazioni, comandi) compaiono come "sistema"
        from .models import RegistroModifica

        RegistroModifica.objects.create(
            azione=RegistroModifica.Azione.choices[0][0], tabella="prova", oggetto_id="1", descrizione="importazione"
        )
        self.assertContains(self.client.get(reverse("registro")), "sistema")

    def test_modifica_scheda_da_form(self):
        self.client.force_login(self.compilatore)
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        scheda = analisi.revisione_corrente.schede.filter(misure__isnull=False).first()
        pagina = self.client.get(reverse("scheda", args=[scheda.pk]))
        html = pagina.content.decode()
        # La decisione del tecnico sta dopo gli allegati, fuori dal form, collegata con form="form-scheda"
        self.assertLess(html.index("9. IMMAGINI ALLEGATE"), html.index("DECISIONE DEL TECNICO"))
        self.assertIn('form="form-scheda"', html[html.index("DECISIONE DEL TECNICO"):])
        dati = {}
        form = pagina.context["form"]
        for nome, campo in form.fields.items():
            valore = form.initial.get(nome)
            if hasattr(valore, "__iter__") and not isinstance(valore, str):
                dati[nome] = [getattr(v, "pk", v) for v in valore]
            elif valore is not None:
                dati[nome] = getattr(valore, "pk", valore)
        misure = pagina.context["misure"]
        dati.update({f"misure-{k}": v for k, v in misure.management_form.initial.items()})
        dati["misure-TOTAL_FORMS"] = misure.initial_form_count()
        for i, mf in enumerate(misure.forms):
            if mf.instance.pk:
                dati.update({f"misure-{i}-id": mf.instance.pk, f"misure-{i}-ordine": 0, f"misure-{i}-tipo": "PROT", f"misure-{i}-testo": mf.instance.testo})
        dati["se_finale"] = 2
        risposta = self.client.post(reverse("scheda", args=[scheda.pk]), dati)
        self.assertEqual(risposta.status_code, 302, risposta.context and (risposta.context["form"].errors, risposta.context["misure"].errors, risposta.context["misure"].non_form_errors()))
        scheda.refresh_from_db()
        self.assertEqual(scheda.se_finale, 2)
        self.assertEqual(scheda.decisione, SchedaAnalisi.Decisione.MODIFICATA)
        self.assertEqual(scheda.misure.first().tipo, "PROT")


class DocumentiTest(BaseConLibreria):
    def setUp(self):
        import tempfile

        from django.test import override_settings

        self.media = tempfile.TemporaryDirectory()
        self.impostazioni = override_settings(MEDIA_ROOT=self.media.name)
        self.impostazioni.enable()
        macchina = self.nuova_macchina()
        macchina.modello = "TR 5/4 CNC"
        macchina.funzione = "Lucidatura automatica di rubinetteria"
        macchina.save()
        from .models import LegislazioneUE

        macchina.altre_legislazioni.set(LegislazioneUE.objects.filter(predefinita=True))
        self.analisi = servizi.crea_analisi_da_libreria(macchina, self.compilatore)
        self.rev = self.analisi.revisione_corrente

    def tearDown(self):
        self.impostazioni.disable()
        self.media.cleanup()

    def test_grassetto_nelle_note(self):
        from . import documenti

        scheda = self.rev.schede.exclude(decisione=SchedaAnalisi.Decisione.SCARTATA).first()
        scheda.note = "Prima parte **molto importante** e coda"
        scheda.save()
        self.assertEqual(
            documenti._pulito("a **b** <c>"), "a <b>b</b> &lt;c&gt;"
        )
        testo = DocumentiTest.leggi(documenti.valutazione(self.rev))
        self.assertIn("Prima parte molto importante e coda", testo)
        self.assertNotIn("**", testo)

    def test_testo_formattato_nel_pdf(self):
        from . import documenti

        scheda = self.rev.schede.exclude(decisione=SchedaAnalisi.Decisione.SCARTATA).first()
        scheda.note = (
            "<b>Grassetto</b> e <i>corsivo</i> e <u>sotto</u> &lt;5 bar"
            "<ul><li>primo</li><li>secondo</li></ul><div>fine</div>"
        )
        scheda.save()
        self.assertEqual(
            documenti._pulito(scheda.note),
            "<b>Grassetto</b> e <i>corsivo</i> e <u>sotto</u> &lt;5 bar<br/>• primo<br/>• secondo<br/>fine",
        )
        testo = DocumentiTest.leggi(documenti.valutazione(self.rev))
        self.assertIn("Grassetto e corsivo e sotto <5 bar", testo)
        self.assertIn("• primo", testo)
        self.assertNotIn("<b>", testo)

    def test_pagina_di_intestazione_con_logo(self):
        from django.core.files.base import ContentFile
        from PIL import Image
        from pypdf import PdfReader

        from . import documenti
        from .models import Fabbricante

        immagine = io.BytesIO()
        Image.new("RGB", (300, 100), "navy").save(immagine, "PNG")
        fabbricante = Fabbricante.objects.first() or Fabbricante.objects.create(
            ragione_sociale="C.O.S.M.A.P. s.r.l.", indirizzo="Saccolongo"
        )
        fabbricante.logo.save("logo.png", ContentFile(immagine.getvalue()))
        pagine = PdfReader(io.BytesIO(documenti.valutazione(self.rev))).pages
        prima = pagine[0]
        self.assertIn("VALUTAZIONE DEI RISCHI", prima.extract_text())
        self.assertNotIn("Definizioni", prima.extract_text())
        self.assertTrue(prima.images, "il logo deve essere nella prima pagina")
        self.assertIn("Definizioni", pagine[1].extract_text())

    @staticmethod
    def leggi(contenuto):
        """Testo del PDF su una riga, con gli spazi normalizzati (gli a capo diventano spazi)."""
        from pypdf import PdfReader

        testo = " ".join(pagina.extract_text() for pagina in PdfReader(io.BytesIO(contenuto)).pages)
        return " ".join(testo.split())

    def approva(self):
        servizi.invia_in_verifica(self.rev, self.compilatore)
        servizi.segna_verificata(self.rev, self.verificatore)
        servizi.approva(self.rev, self.approvatore)

    def test_dichiarazione_bozza_e_definitiva(self):
        from . import documenti

        bozza = self.leggi(documenti.dichiarazione(self.rev))
        self.assertIn("BOZZA", bozza)
        self.assertIn("Regolamento (UE) 2023/1230", bozza)
        self.assertIn("C.O.S.M.A.P. s.r.l.", bozza)
        self.assertIn("2014/30/UE", bozza)
        self.assertIn("Lucidatura automatica di rubinetteria", bozza)
        self.assertIn("EN ISO 12100", bozza)

        self.approva()
        definitiva = self.leggi(documenti.dichiarazione(self.rev, "en"))
        self.assertNotIn("DRAFT", definitiva)
        self.assertIn("EU Declaration of Conformity", definitiva)
        self.assertIn("Saccolongo", definitiva)

    def test_valutazione_e_residui(self):
        from . import documenti

        scheda = self.rev.schede.exclude(testo_istruzioni="").first()
        servizi.decidi_scheda(scheda, self.compilatore, SchedaAnalisi.Decisione.SCARTATA, "Non presente sulla macchina")
        valutazione = self.leggi(documenti.valutazione(self.rev))
        self.assertIn("Metodo di stima", valutazione)
        self.assertIn("Non presente sulla macchina", valutazione)
        self.assertIn("Misure richieste", valutazione)
        residui = self.leggi(documenti.rischi_residui(self.rev))
        self.assertIn("Rischi residui", residui)
        altra = self.rev.schede.exclude(pk=scheda.pk).exclude(testo_istruzioni="").first()
        self.assertIn(altra.testo_istruzioni[:40], residui)

    def test_stime_con_descrizione(self):
        from . import documenti

        scheda = self.rev.schede.exclude(se_iniziale=None).first()
        self.client.force_login(self.compilatore)
        pagina = self.client.get(reverse("scheda", args=[scheda.pk]))
        self.assertContains(pagina, "4 – Morte")
        self.assertContains(pagina, "3 – Possibile")
        valutazione = self.leggi(documenti.valutazione(self.rev))
        self.assertIn("Valori dei fattori", valutazione)
        se = self.rev.metodo.descrizioni()[("Se", scheda.se_iniziale)]
        self.assertIn(f"{scheda.se_iniziale} – {se}", valutazione)

    def test_genera_da_pagina_e_archivia(self):
        from .models import DocumentoGenerato

        self.client.force_login(self.compilatore)
        risposta = self.client.post(reverse("genera_documento", args=[self.rev.pk, "dichiarazione"]), {"lingua": "en"})
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("_BOZZA_en.pdf", risposta["Content-Disposition"])
        self.assertEqual(risposta["Content-Type"], "application/pdf")
        risposta.close()  # su Windows un file aperto non si può cancellare
        documento = DocumentoGenerato.objects.get()
        self.assertFalse(documento.definitivo)
        pagina = self.client.get(reverse("analisi", args=[self.analisi.pk]))
        self.assertContains(pagina, 'target="_blank">Apri</a>')
        scaricato = self.client.get(reverse("scarica_documento", args=[documento.pk]))
        self.assertEqual(scaricato.status_code, 200)
        self.assertTrue(scaricato["Content-Disposition"].startswith("inline"))  # si apre nella nuova scheda
        scaricato.close()

        self.approva()
        self.client.post(reverse("genera_documento", args=[self.rev.pk, "valutazione"])).close()
        self.assertTrue(DocumentoGenerato.objects.get(tipo="VALUTAZIONE").definitivo)


class ModuliDellaMacchinaTest(BaseConLibreria):
    def setUp(self):
        self.macchina = self.nuova_macchina()
        self.analisi = servizi.crea_analisi_da_libreria(self.macchina, self.compilatore)
        self.rev = self.analisi.revisione_corrente
        self.tavola = Modulo.objects.filter(nome__startswith="Tavola rotante").first()

    def test_aggiunge_e_toglie_moduli(self):
        moduli = list(self.macchina.moduli.all())
        aggiunte, tolte, rimaste = servizi.cambia_moduli(self.macchina, moduli + [self.tavola], self.compilatore)
        self.assertEqual(aggiunte, SchedaModello.objects.filter(modulo=self.tavola).count())
        self.assertEqual((tolte, rimaste), (0, 0))

        decisa = self.rev.schede.filter(modulo=self.tavola).first()
        servizi.decidi_scheda(decisa, self.compilatore, SchedaAnalisi.Decisione.CONFERMATA, "")
        aggiunte, tolte, rimaste = servizi.cambia_moduli(self.macchina, moduli, self.compilatore)
        self.assertEqual((aggiunte, rimaste), (0, 1))
        self.assertEqual(self.rev.schede.filter(modulo=self.tavola).count(), 1)
        self.assertNotIn(self.tavola, self.macchina.moduli.all())

    def test_escludere_e_riattivare_una_scheda(self):
        moduli = list(self.macchina.moduli.all())
        scheda = self.rev.schede.filter(decisione=SchedaAnalisi.Decisione.PROPOSTA).exclude(origine=None).first()
        modello = scheda.origine
        aggiunte, tolte, rimaste = servizi.cambia_moduli(self.macchina, moduli, self.compilatore, [modello])
        self.assertEqual((aggiunte, tolte, rimaste), (0, 1, 0))
        self.assertFalse(self.rev.schede.filter(origine=modello).exists())
        self.assertNotIn(modello, servizi.schede_attive(self.macchina))
        aggiunte, tolte, rimaste = servizi.cambia_moduli(self.macchina, moduli, self.compilatore, [])
        self.assertEqual((aggiunte, tolte, rimaste), (1, 0, 0))
        self.assertTrue(self.rev.schede.filter(origine=modello).exists())

    def test_schede_escluse_dalla_pagina_della_macchina(self):
        self.client.force_login(self.compilatore)
        url = reverse("macchina", args=[self.macchina.pk])
        moduli = list(self.macchina.moduli.all()) + [self.tavola]
        schede_tavola = list(SchedaModello.objects.filter(modulo=self.tavola))
        attive = list(SchedaModello.objects.values_list("pk", flat=True))
        esclusa = schede_tavola[0]
        attive.remove(esclusa.pk)
        self.client.post(url, {
            "denominazione": self.macchina.denominazione, "tipo": self.macchina.tipo, "con_schede": "True",
            "moduli": [x.pk for x in moduli], "schede": attive,
        })
        self.assertEqual(list(self.macchina.schede_escluse.all()), [esclusa])
        self.assertEqual(self.rev.schede.filter(modulo=self.tavola).count(), len(schede_tavola) - 1)
        self.assertFalse(self.rev.schede.filter(origine=esclusa).exists())
        # Nella pagina la scheda esclusa compare senza spunta
        pagina = self.client.get(url).content.decode()
        self.assertIn(f'name="schede" value="{esclusa.pk}">', pagina)

    def test_non_si_cambiano_con_revisione_approvata(self):
        servizi.invia_in_verifica(self.rev, self.compilatore)
        servizi.segna_verificata(self.rev, self.verificatore)
        servizi.approva(self.rev, self.approvatore)
        with self.assertRaises(ValidationError):
            servizi.cambia_moduli(self.macchina, [self.tavola], self.compilatore)

    def test_dalla_pagina_della_macchina(self):
        self.client.force_login(self.compilatore)
        url = reverse("macchina", args=[self.macchina.pk])
        self.assertContains(self.client.get(url), "MODULI E SCHEDE MODELLO")
        risposta = self.client.post(
            url,
            {
                "denominazione": self.macchina.denominazione,
                "tipo": self.macchina.tipo,
                "moduli": [m.pk for m in self.macchina.moduli.all()] + [self.tavola.pk],
            },
        )
        self.assertRedirects(risposta, reverse("analisi", args=[self.analisi.pk]))
        self.assertIn(self.tavola, self.macchina.moduli.all())
        self.assertTrue(self.rev.schede.filter(modulo=self.tavola).exists())


    def test_requisiti_non_considerati_dalla_pagina_della_macchina(self):
        from .models import RequisitoRESS

        self.client.force_login(self.compilatore)
        url = reverse("macchina", args=[self.macchina.pk])
        self.assertContains(self.client.get(url), "REQUISITI RESS DA CONSIDERARE")
        scheda = self.rev.schede.filter(decisione=SchedaAnalisi.Decisione.PROPOSTA).exclude(origine=None).first()
        escluso = scheda.requisito
        tutti = list(RequisitoRESS.objects.filter(riferimento=escluso.riferimento).values_list("pk", flat=True))
        dati = {
            "denominazione": self.macchina.denominazione, "tipo": self.macchina.tipo, "con_requisiti": "True",
            "moduli": [x.pk for x in self.macchina.moduli.all()],
        }
        self.client.post(url, {**dati, "requisiti": [pk for pk in tutti if pk != escluso.pk]})
        self.assertEqual(list(self.macchina.requisiti_esclusi.all()), [escluso])
        self.assertFalse(self.rev.schede.filter(requisito=escluso, decisione=SchedaAnalisi.Decisione.PROPOSTA).exists())
        voce = self.rev.applicabilita.get(requisito=escluso)
        self.assertFalse(voce.applicabile)
        self.assertEqual(voce.motivazione, servizi.MOTIVO_NON_CONSIDERATO)
        # Considerato di nuovo: torna applicabile e le sue schede tornano proposte
        self.client.post(url, {**dati, "requisiti": tutti})
        voce.refresh_from_db()
        self.assertTrue(voce.applicabile)
        self.assertEqual(voce.motivazione, "")
        self.assertTrue(self.rev.schede.filter(origine=scheda.origine).exists())


class AmministrazioneLibreriaTest(BaseConLibreria):
    def test_pagina_modulo_elenca_le_schede_senza_spostarle(self):
        admin_utente = User.objects.create_superuser("capo", password="prova-prova-123")
        self.client.force_login(admin_utente)
        robot = Modulo.objects.get(nome__startswith="Gruppo di smerigliatura")
        pagina = self.client.get(reverse("admin:rischi_modulo_change", args=[robot.pk]))
        self.assertContains(pagina, "Schede del modulo")
        self.assertContains(pagina, robot.schede.first().codice)
        self.assertNotContains(pagina, 'name="schede"')


class CodiciPerModuloTest(TestCase):
    def test_codici_con_sigla_e_numero_nel_modulo(self):
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        tavola = Modulo.objects.get(nome__startswith="Tavola")
        self.assertEqual(tavola.sigla, "TAV")
        codici = sorted(tavola.schede.values_list("codice", flat=True))
        self.assertEqual(codici, [f"TAV-{n:02d}" for n in range(1, len(codici) + 1)])
        # L'ordine di visualizzazione segue il requisito RESS, non il numero della scheda
        requisiti = [s.requisito.ordine for s in Modulo.objects.get(sigla="ELE").schede.all()]
        self.assertEqual(requisiti, sorted(requisiti))
        self.assertFalse(SchedaModello.objects.filter(codice__startswith="NL-").exists())


class EliminaCommessaTest(BaseConLibreria):
    def setUp(self):
        self.analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina("26-99"), self.compilatore)
        self.commessa = self.analisi.macchina.commessa
        self.url = reverse("elimina_commessa", args=[self.commessa.pk])

    def test_bozza_si_elimina_con_il_numero(self):
        self.client.force_login(self.compilatore)
        self.assertContains(self.client.get(reverse("analisi", args=[self.analisi.pk])), "Elimina commessa")
        self.client.post(self.url, {"conferma": "sbagliato"})
        self.assertTrue(Commessa.objects.filter(pk=self.commessa.pk).exists())

        risposta = self.client.post(self.url, {"conferma": "26-99"})
        self.assertRedirects(risposta, reverse("elenco_commesse"))
        self.assertFalse(Commessa.objects.filter(numero="26-99").exists())
        self.assertFalse(SchedaAnalisi.objects.exists())
        eliminate = RegistroModifica.objects.filter(azione=RegistroModifica.Azione.ELIMINA)
        self.assertTrue(eliminate.filter(tabella="commessa").exists())
        self.assertFalse(eliminate.filter(tabella="scheda dell'analisi").exists())

    def test_approvata_solo_dall_approvatore(self):
        from . import documenti
        from .models import DocumentoGenerato

        rev = self.analisi.revisione_corrente
        servizi.invia_in_verifica(rev, self.compilatore)
        servizi.segna_verificata(rev, self.verificatore)
        servizi.approva(rev, self.approvatore)
        DocumentoGenerato.objects.create(
            revisione=rev, tipo="VALUTAZIONE", lingua="it", definitivo=True, generato_da=self.compilatore,
            file="documenti/prova.pdf",
        )
        # Il compilatore non può più eliminarla
        self.client.force_login(self.compilatore)
        self.assertNotContains(self.client.get(reverse("analisi", args=[self.analisi.pk])), "Elimina commessa")
        self.client.post(self.url, {"conferma": "26-99"})
        self.assertTrue(Commessa.objects.filter(pk=self.commessa.pk).exists())
        with self.assertRaises(PermissionDenied):
            servizi.elimina_commessa(self.commessa, self.compilatore)
        # L'approvatore sì, con l'avviso sulle revisioni approvate
        self.client.force_login(self.approvatore)
        pagina = self.client.get(reverse("analisi", args=[self.analisi.pk]))
        self.assertContains(pagina, "Elimina commessa")
        self.assertContains(pagina, "revisioni <strong>approvate</strong>")
        risposta = self.client.post(self.url, {"conferma": "26-99"})
        self.assertRedirects(risposta, reverse("elenco_commesse"))
        self.assertFalse(Commessa.objects.filter(numero="26-99").exists())
        self.assertFalse(Revisione.objects.exists())
        self.assertFalse(DocumentoGenerato.objects.exists())

    def test_serve_il_compilatore(self):
        with self.assertRaises(PermissionDenied):
            servizi.elimina_commessa(self.commessa, self.verificatore)
        self.assertTrue(Commessa.objects.filter(pk=self.commessa.pk).exists())


class SoggettiEspostiTest(TestCase):
    """Soggetti esposti (RESS 1.1.1 c e d): libreria, macchina, schede, controlli e documento."""

    @classmethod
    def setUpTestData(cls):
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        cls.compilatore = crea_utente("mario", servizi.COMPILATORE)
        commessa = Commessa.objects.create(
            numero="26-50", cliente=Cliente.objects.create(ragione_sociale="Prova"), anno=2026,
            riferimento=RiferimentoNormativo.objects.get(),
        )
        cls.macchina = Macchina.objects.create(commessa=commessa, denominazione="Linea", matricola="S1")
        cls.macchina.moduli.set(servizi.moduli_proposti() | Modulo.objects.filter(nome__startswith="Tavola"))
        cls.analisi = servizi.crea_analisi_da_libreria(cls.macchina, cls.compilatore)

    def test_libreria_precompila_i_soggetti(self):
        from .models import Figura

        self.assertEqual(Figura.objects.count(), 8)
        carico = SchedaModello.objects.get(codice="TAV-01")
        self.assertIn("Operatore di conduzione", [f.nome for f in carico.soggetti.all()])
        quadro = SchedaModello.objects.get(codice="ELE-01")
        self.assertEqual([f.nome for f in quadro.soggetti.all()], ["Manutentore elettrico"])

    def test_soggetti_copiati_e_figure_della_macchina(self):
        rev = self.analisi.revisione_corrente
        scheda = rev.schede.get(codice="TAV-01")
        self.assertIn("Operatore di conduzione", [f.nome for f in scheda.soggetti.all()])
        figure = {f.figura.nome: f.descrizione for f in self.macchina.figure.select_related("figura")}
        self.assertIn("Operatore di conduzione", figure)
        self.assertTrue(figure["Operatore di conduzione"])

    def test_controllo_schede_senza_soggetti(self):
        rev = self.analisi.revisione_corrente
        self.assertFalse([a for a in servizi.controlli(rev) if a.tipo == "soggetti"])
        scheda = rev.schede.get(codice="TAV-01")
        scheda.soggetti.clear()
        segnalate = [a.scheda for a in servizi.controlli(rev) if a.tipo == "soggetti"]
        self.assertEqual(segnalate, [scheda])

    def test_dati_macchina_senza_soggetti_e_documento(self):
        from . import documenti
        from .models import Figura

        self.client.force_login(self.compilatore)
        # Le figure si gestiscono solo nella libreria: la pagina della macchina non le mostra più
        pagina = self.client.get(reverse("macchina", args=[self.macchina.pk]))
        self.assertNotContains(pagina, "figure-TOTAL_FORMS")
        risposta = self.client.post(reverse("macchina", args=[self.macchina.pk]), {
            "denominazione": "Linea", "matricola": "S1", "tipo": "MACCHINA",
            "moduli": [m.pk for m in self.macchina.moduli.all()],
        })
        self.assertEqual(risposta.status_code, 302)
        self.assertTrue(self.macchina.figure.filter(figura__nome="Operatore di conduzione").exists())

        scheda = self.analisi.revisione_corrente.schede.get(codice="TAV-01")
        pagina = self.client.get(reverse("scheda", args=[scheda.pk]))
        self.assertContains(pagina, "Operatore di conduzione")

        terzi = self.macchina.figure.get(figura=Figura.objects.get(nome="Terzi di passaggio"))
        terzi.descrizione = "Mulettista che transita nella corsia adiacente"
        terzi.save()
        testo = DocumentiTest.leggi(documenti.valutazione(self.analisi.revisione_corrente))
        self.assertIn("Soggetti esposti", testo)
        self.assertIn("Mulettista che transita nella corsia adiacente", testo)
        self.assertIn("Persona esposta (RESS 1.1.1 c)", testo)

    def test_testi_piu_lunghi_di_una_pagina(self):
        """Note e considerazioni più alte di una pagina proseguono sulla pagina seguente invece di dare errore."""
        from . import documenti

        scheda = self.analisi.revisione_corrente.schede.get(codice="TAV-01")
        lungo = "\n".join(f"Riga {i} di un testo molto lungo che occupa parecchio spazio nella pagina." for i in range(80))
        scheda.note = scheda.considerazioni_riduzione = scheda.testo_istruzioni = lungo
        scheda.save()
        testo = DocumentiTest.leggi(documenti.valutazione(self.analisi.revisione_corrente))
        self.assertIn("Riga 79 di un testo molto lungo", testo)
        documenti.rischi_residui(self.analisi.revisione_corrente)

    def test_considerazioni_nel_pdf(self):
        from . import documenti

        scheda = self.analisi.revisione_corrente.schede.get(codice="TAV-01")
        scheda.considerazioni_limiti = "Zona di carico raggiungibile dal lato operatore"
        scheda.considerazioni_riduzione = "Riparo fisso scelto per la frequenza bassa di accesso"
        scheda.save()
        from .models import Norma

        norma = Norma.objects.create(codice="EN ISO 99999", titolo="Norma di prova per la sezione 1")
        scheda.norme.add(norma)
        misura = scheda.misure.first()
        misura.norma = Norma.objects.create(codice="EN ISO 88888", titolo="Norma di prova della misura")
        misura.save()
        testo = DocumentiTest.leggi(documenti.valutazione(self.analisi.revisione_corrente))
        self.assertIn("Zona di carico raggiungibile dal lato operatore", testo)
        self.assertIn("Riparo fisso scelto per la frequenza bassa di accesso", testo)
        norme = testo.index("EN ISO 99999")
        # Le norme delle misure stanno nella sezione 6, con codice e titolo come nella sezione 1
        norma_misura = testo.index("EN ISO 88888 – Norma di prova della misura")
        self.assertLess(testo.rindex("6. RIDUZIONE DEL RISCHIO", 0, norma_misura), norma_misura)
        self.assertLess(norma_misura, testo.index("7. STIMA FINALE", norma_misura))
        self.assertLess(testo.rindex("1. IDENTIFICAZIONE SCHEDA", 0, norme), norme)
        self.assertLess(norme, testo.index("2. IDENTIFICAZIONE DEL PERICOLO", norme))
        self.assertIn("3. IDENTIFICAZIONE DELLA ZONA PERICOLOSA (RESS 1.1.1 b)", testo)
        # Le considerazioni stanno nella loro sezione, prima della sezione successiva della stessa scheda
        posizione = testo.index("Zona di carico raggiungibile")
        self.assertLess(testo.rindex("3. IDENTIFICAZIONE DELLA ZONA PERICOLOSA", 0, posizione), posizione)
        self.assertLess(posizione, testo.index("Riparo fisso scelto", posizione))

    def test_completa_soggetti_nelle_bozze(self):
        rev = self.analisi.revisione_corrente
        for scheda in rev.schede.all():
            scheda.soggetti.clear()
        self.macchina.figure.all().delete()
        call_command("completa_soggetti", stdout=io.StringIO())
        self.assertFalse([a for a in servizi.controlli(rev) if a.tipo == "soggetti"])
        self.assertTrue(self.macchina.figure.filter(figura__nome="Operatore di conduzione").exists())


class CodiceAutomaticoTest(TestCase):
    """Il codice delle schede modello si genera da solo: SIGLA-NN."""

    @classmethod
    def setUpTestData(cls):
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        cls.capo = User.objects.create_superuser("capo", password="prova-prova-123")

    def dati(self, modulo, requisito):
        return {
            "modulo": modulo.pk, "requisito": requisito.pk, "stato": "BOZZA",
            "misure-TOTAL_FORMS": 0, "misure-INITIAL_FORMS": 0, "misure-MIN_NUM_FORMS": 0, "misure-MAX_NUM_FORMS": 1000,
            "allegati-TOTAL_FORMS": 0, "allegati-INITIAL_FORMS": 0, "allegati-MIN_NUM_FORMS": 0, "allegati-MAX_NUM_FORMS": 1000,
        }

    def test_nuova_scheda_e_cambio_di_modulo(self):
        from .models import RequisitoRESS

        self.client.force_login(self.capo)
        tavola = Modulo.objects.get(sigla="TAV")
        requisito = RequisitoRESS.objects.get(codice="1.3.8.2")
        risposta = self.client.post(reverse("admin:rischi_schedamodello_add"), self.dati(tavola, requisito))
        self.assertEqual(risposta.status_code, 302)
        nuova = SchedaModello.objects.get(codice="TAV-06")

        cabina = Modulo.objects.get(sigla="CAB")
        url = reverse("admin:rischi_schedamodello_change", args=[nuova.pk])
        self.assertEqual(self.client.post(url, self.dati(cabina, requisito)).status_code, 302)
        nuova.refresh_from_db()
        self.assertEqual(nuova.codice, "CAB-08")

    def test_norme_della_sezione_1(self):
        from .models import Norma, RequisitoRESS

        self.client.force_login(self.capo)
        prima, seconda = Norma.objects.order_by("codice")[:2]
        dati = self.dati(Modulo.objects.get(sigla="TAV"), RequisitoRESS.objects.get(codice="1.3.8.2"))
        dati.update({"norma_1": seconda.pk, "norma_2": prima.pk, "norma_3": seconda.pk})
        self.assertEqual(self.client.post(reverse("admin:rischi_schedamodello_add"), dati).status_code, 302)
        nuova = SchedaModello.objects.get(codice="TAV-06")
        self.assertEqual(set(nuova.norme.all()), {prima, seconda})

        # Le cinque selezioni stanno sotto le note e ripropongono le norme salvate, in ordine di codice
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[nuova.pk])).content.decode()
        posizioni = [pagina.index(t) for t in ['name="note"', *(f'name="norma_{i}"' for i in range(1, 6)), "2. IDENTIFICAZIONE"]]
        self.assertEqual(posizioni, sorted(posizioni))
        self.assertIn(f'<option value="{prima.pk}" selected>', pagina[pagina.index('name="norma_1"'):pagina.index('name="norma_2"')])

    def test_modulo_senza_sigla(self):
        from .models import RequisitoRESS

        self.client.force_login(self.capo)
        senza = Modulo.objects.create(nome="Modulo senza sigla")
        risposta = self.client.post(
            reverse("admin:rischi_schedamodello_add"), self.dati(senza, RequisitoRESS.objects.get(codice="1.1.3"))
        )
        self.assertContains(risposta, "non ha la sigla")
        self.assertFalse(SchedaModello.objects.filter(modulo=senza).exists())

    def test_codice_dal_modello(self):
        from .models import RequisitoRESS

        elettrico = Modulo.objects.get(sigla="ELE")
        scheda = SchedaModello.objects.create(modulo=elettrico, requisito=RequisitoRESS.objects.get(codice="1.5.1"))
        self.assertEqual(scheda.codice, "ELE-05")


class CodiceSchedeAggiunteTest(TestCase):
    """Anche le schede aggiunte a mano nell'analisi prendono il codice SIGLA-NN."""

    @classmethod
    def setUpTestData(cls):
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        cls.compilatore = crea_utente("mario", servizi.COMPILATORE)
        commessa = Commessa.objects.create(
            numero="26-70", cliente=Cliente.objects.create(ragione_sociale="Prova"), anno=2026,
            riferimento=RiferimentoNormativo.objects.get(),
        )
        cls.macchina = Macchina.objects.create(commessa=commessa, denominazione="Linea")
        cls.macchina.moduli.set(servizi.moduli_proposti() | Modulo.objects.filter(sigla="TAV"))
        cls.analisi = servizi.crea_analisi_da_libreria(cls.macchina, cls.compilatore)

    def dati(self, modulo, requisito, decisione="AGGIUNTA"):
        return {
            "modulo": modulo.pk, "requisito": requisito.pk, "decisione": decisione,
            "misure-TOTAL_FORMS": 0, "misure-INITIAL_FORMS": 0, "misure-MIN_NUM_FORMS": 0, "misure-MAX_NUM_FORMS": 1000,
        }

    def test_nuova_scheda_e_cambio_di_requisito(self):
        from .models import Norma, RequisitoRESS

        self.client.force_login(self.compilatore)
        rev = self.analisi.revisione_corrente
        tavola = Modulo.objects.get(sigla="TAV")
        risposta = self.client.post(
            reverse("nuova_scheda", args=[rev.pk]), self.dati(tavola, RequisitoRESS.objects.get(codice="1.3.8.2"))
        )
        self.assertEqual(risposta.status_code, 302, getattr(risposta, "context", None) and risposta.context["form"].errors)
        nuova = rev.schede.get(decisione=SchedaAnalisi.Decisione.AGGIUNTA)
        self.assertEqual(nuova.codice, "TAV-06")
        self.assertFalse(nuova.norme.exists())
        norma = Norma.objects.order_by("codice").first()
        self.client.post(reverse("scheda", args=[nuova.pk]), {**self.dati(tavola, nuova.requisito), "norma_1": norma.pk})
        self.assertEqual(list(nuova.norme.all()), [norma])

        # Una seconda scheda nel modulo prende il numero successivo
        self.client.post(reverse("nuova_scheda", args=[rev.pk]), self.dati(tavola, RequisitoRESS.objects.get(codice="1.1.6")))
        self.assertTrue(rev.schede.filter(codice="TAV-07").exists())

        # Cambiando requisito il codice resta; cambiando modulo prende il numero successivo nel nuovo modulo
        url = reverse("scheda", args=[nuova.pk])
        self.client.post(url, self.dati(tavola, RequisitoRESS.objects.get(codice="1.1.6")))
        nuova.refresh_from_db()
        self.assertEqual(nuova.codice, "TAV-06")
        generale = Modulo.objects.get(sigla="GEN")
        self.client.post(url, self.dati(generale, RequisitoRESS.objects.get(codice="1.1.6")))
        nuova.refresh_from_db()
        self.assertEqual(nuova.codice, "GEN-17")

    def test_modulo_senza_sigla(self):
        from .models import RequisitoRESS

        self.client.force_login(self.compilatore)
        rev = self.analisi.revisione_corrente
        senza = Modulo.objects.create(nome="Senza sigla")
        risposta = self.client.post(
            reverse("nuova_scheda", args=[rev.pk]), self.dati(senza, RequisitoRESS.objects.get(codice="1.1.3"))
        )
        self.assertContains(risposta, "non ha la sigla")
        self.assertFalse(rev.schede.filter(modulo=senza).exists())


class LibreriaAmministrazioneTest(TestCase):
    """Scheda modello con i fattori descritti; sigla del modulo che rinomina le schede."""

    @classmethod
    def setUpTestData(cls):
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        cls.capo = User.objects.create_superuser("capo", password="prova-prova-123")

    def test_fattori_con_descrizione_nella_scheda_modello(self):
        self.client.force_login(self.capo)
        scheda = SchedaModello.objects.get(codice="TAV-01")
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[scheda.pk]))
        self.assertContains(pagina, "Se – Gravità")
        descrizione = MetodoStima.corrente().descrizioni()[("Se", scheda.se_iniziale)]
        self.assertContains(pagina, f"{scheda.se_iniziale} – {descrizione}")

    def test_scheda_modello_nello_stesso_ordine_dell_analisi(self):
        self.client.force_login(self.capo)
        scheda = SchedaModello.objects.get(codice="TAV-01")
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[scheda.pk])).content.decode()
        titoli = [
            "1. IDENTIFICAZIONE SCHEDA MODELLO",
            "2. IDENTIFICAZIONE DEL PERICOLO (RESS 1.1.1 a)",
            'name="considerazioni_pericoli"',
            'name="pericoli"',
            "3. IDENTIFICAZIONE DELLA ZONA PERICOLOSA (RESS 1.1.1 b)",
            'name="considerazioni_limiti"',
            'name="condizioni"',
            "4. IDENTIFICAZIONE DEI SOGGETTI ESPOSTI (RESS 1.1.1 c, d)",
            'name="considerazioni_soggetti"',
            'name="soggetti"',
            "5. STIMA INIZIALE DEL RISCHIO (RESS 1.1.1 e)",
            "6. RIDUZIONE DEL RISCHIO (RESS 1.1.1 f, g)",
            'name="considerazioni_riduzione"',
            'name="misure-0-testo"',
            "7. STIMA FINALE DEL RISCHIO (RESS 1.1.1 e)",
            "8. VALUTAZIONE DEL RISCHIO RESIDUO",
        ]
        posizioni = [pagina.index(t) for t in titoli]
        self.assertEqual(posizioni, sorted(posizioni))
        self.assertIn('type="checkbox" name="condizioni"', pagina)
        self.assertIn('type="checkbox" name="soggetti"', pagina)
        self.assertEqual(pagina.count('name="considerazioni_'), 6)
        # Una sola sezione 6: le misure e le considerazioni sotto lo stesso titolo
        self.assertEqual(pagina.count("6. RIDUZIONE DEL RISCHIO"), 1)
        self.assertEqual(pagina.count(">Considerazioni:<"), 6)
        # Riferimenti al RESS solo nei titoli delle sezioni; le norme si leggono dalle misure
        self.assertNotIn("(RESS 1.1.1 a)</label>", pagina)
        self.assertNotIn('name="norme"', pagina)
        self.assertIn("rischi/admin_scheda.css", pagina)

    def test_scheda_modello_mostra_cl_ed_esito(self):
        self.client.force_login(self.capo)
        scheda = SchedaModello.objects.filter(se_iniziale__isnull=False, fr_iniziale__isnull=False).first()
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[scheda.pk]))
        self.assertContains(pagina, f"= <b>{scheda.cl_iniziale}</b>")
        self.assertContains(pagina, "Classe ed esito finale")

    def test_pericoli_secondo_iso_12100(self):
        codici = set(Pericolo.objects.values_list("codice", flat=True))
        self.assertTrue(codici)
        self.assertTrue(all(c.count(".") == 2 for c in codici), codici)
        self.assertIn("1.2.1", codici)

    def dati_modulo(self, modulo, sigla):
        return {
            "nome": modulo.nome, "sigla": sigla, "descrizione": modulo.descrizione, "condizione": modulo.condizione,
            "attivo": "on", "ordine": modulo.ordine,
        }

    def test_cambio_sigla_rinomina_le_schede(self):
        self.client.force_login(self.capo)
        tavola = Modulo.objects.get(sigla="TAV")
        quante = tavola.schede.count()
        url = reverse("admin:rischi_modulo_change", args=[tavola.pk])
        risposta = self.client.post(url, self.dati_modulo(tavola, "trt"))
        self.assertEqual(risposta.status_code, 302)
        codici = sorted(tavola.schede.values_list("codice", flat=True))
        self.assertEqual(codici, [f"TRT-{n:02d}" for n in range(1, quante + 1)])

        risposta = self.client.post(url, self.dati_modulo(tavola, "CAB"))
        self.assertContains(risposta, "già usata da un altro modulo")
        self.assertTrue(tavola.schede.filter(codice="TRT-01").exists())

    def test_cambio_sigla_con_schede_di_un_prefisso_diverso(self):
        # Le schede hanno ancora la sigla di partenza, la sigla del modulo è già stata cambiata prima
        self.client.force_login(self.capo)
        lucidatura = Modulo.objects.get(sigla="LUC")
        Modulo.objects.filter(pk=lucidatura.pk).update(sigla="UPL")
        lucidatura.refresh_from_db()
        url = reverse("admin:rischi_modulo_change", args=[lucidatura.pk])
        self.assertEqual(self.client.post(url, self.dati_modulo(lucidatura, "UPP")).status_code, 302)
        codici = sorted(lucidatura.schede.values_list("codice", flat=True))
        self.assertEqual(codici, [f"UPP-{n:02d}" for n in range(1, len(codici) + 1)])


class AggiornaDaModelloTest(TestCase):
    """La scheda della commessa si ricarica dalla scheda modello aggiornata in libreria."""

    @classmethod
    def setUpTestData(cls):
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        cls.compilatore = crea_utente("mario", servizi.COMPILATORE)
        cls.capo = User.objects.create_superuser("capo", password="prova-prova-123")
        commessa = Commessa.objects.create(
            numero="26-80", cliente=Cliente.objects.create(ragione_sociale="Prova"), anno=2026,
            riferimento=RiferimentoNormativo.objects.get(),
        )
        cls.macchina = Macchina.objects.create(commessa=commessa, denominazione="Linea")
        cls.macchina.moduli.set(servizi.moduli_proposti() | Modulo.objects.filter(sigla="TAV"))
        cls.analisi = servizi.crea_analisi_da_libreria(cls.macchina, cls.compilatore)

    def test_aggiorna_la_scheda_dal_modello(self):
        from .models import MisuraModello, Norma

        scheda = self.analisi.revisione_corrente.schede.get(codice="TAV-01")
        modello = scheda.origine
        modello.zona_pericolosa = "Zona aggiornata in libreria"
        modello.considerazioni_riduzione = "Considerazione nuova"
        modello.save()
        norma = Norma.objects.create(codice="EN ISO 77777")
        modello.norme.set([norma])
        modello.misure.all().delete()
        MisuraModello.objects.create(scheda=modello, ordine=1, tipo="PROT", testo="Riparo nuovo", norma=norma)
        scheda.zona_impianto = "Modifica fatta in commessa"
        scheda.save()

        url = reverse("aggiorna_da_modello", args=[scheda.pk])
        # Senza il ruolo di compilatore non cambia nulla
        altro = User.objects.create_user("ospite", password="prova-prova-123")
        self.client.force_login(altro)
        self.assertNotContains(self.client.get(reverse("scheda", args=[scheda.pk])), "Aggiorna dalla scheda modello")
        self.client.post(url)
        scheda.refresh_from_db()
        self.assertNotEqual(scheda.zona_pericolosa, "Zona aggiornata in libreria")

        self.client.force_login(self.compilatore)
        self.assertContains(self.client.get(reverse("scheda", args=[scheda.pk])), "Aggiorna dalla scheda modello TAV-01")
        self.assertRedirects(self.client.post(url), reverse("scheda", args=[scheda.pk]))
        scheda.refresh_from_db()
        self.assertEqual(scheda.codice, "TAV-01")
        self.assertEqual(scheda.zona_pericolosa, "Zona aggiornata in libreria")
        self.assertEqual(scheda.zona_impianto, modello.zona_impianto)
        self.assertEqual(scheda.considerazioni_riduzione, "Considerazione nuova")
        self.assertEqual(list(scheda.norme.all()), [norma])
        self.assertEqual([(m.testo, m.norma) for m in scheda.misure.all()], [("Riparo nuovo", norma)])

    def test_scheda_aggiunta_a_mano_senza_pulsante(self):
        from .models import RequisitoRESS

        rev = self.analisi.revisione_corrente
        scheda = SchedaAnalisi.objects.create(
            revisione=rev, modulo=Modulo.objects.get(sigla="TAV"), requisito=RequisitoRESS.objects.get(codice="1.1.6"),
            codice="TAV-90", decisione=SchedaAnalisi.Decisione.AGGIUNTA, zona_impianto="Tavola",
        )
        self.client.force_login(self.compilatore)
        self.assertNotContains(self.client.get(reverse("scheda", args=[scheda.pk])), "Aggiorna dalla scheda modello")
        self.client.post(reverse("aggiorna_da_modello", args=[scheda.pk]))
        scheda.refresh_from_db()
        self.assertEqual(scheda.zona_impianto, "Tavola")


class LibreriaAzioniTest(BaseConLibreria):
    def setUp(self):
        self.capo = User.objects.create_superuser("capo", password="prova-prova-123")
        self.client.force_login(self.capo)

    def test_duplica_una_scheda_modello(self):
        originale = SchedaModello.objects.filter(misure__isnull=False).distinct().first()
        originale.modulo.sigla = "GEN"
        originale.modulo.save()
        url = reverse("admin:rischi_schedamodello_changelist")
        risposta = self.client.post(url, {"action": "duplica", "_selected_action": [originale.pk]})
        copia = SchedaModello.objects.order_by("-pk").first()
        self.assertRedirects(risposta, reverse("admin:rischi_schedamodello_change", args=[copia.pk]))
        self.assertNotEqual(copia.codice, originale.codice)
        self.assertEqual(copia.modulo, originale.modulo)
        self.assertEqual(copia.misure.count(), originale.misure.count())
        self.assertEqual(set(copia.pericoli.all()), set(originale.pericoli.all()))

    def test_duplica_voci_con_nome_univoco(self):
        from .models import Figura, Norma

        norma = Norma.objects.first()
        self.client.post(reverse("admin:rischi_norma_changelist"), {"action": "duplica", "_selected_action": [norma.pk]})
        self.assertTrue(Norma.objects.filter(codice=f"{norma.codice} (copia)").exists())
        figura = Figura.objects.create(nome="Operatore prova")
        url = reverse("admin:rischi_figura_changelist")
        self.client.post(url, {"action": "duplica", "_selected_action": [figura.pk]})
        self.client.post(url, {"action": "duplica", "_selected_action": [figura.pk]})
        self.assertTrue(Figura.objects.filter(nome="Operatore prova (copia 2)").exists())

    def test_scheda_modello_solo_occhio_sui_collegati(self):
        scheda = SchedaModello.objects.first()
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[scheda.pk])).content.decode()
        self.assertIn("view-related", pagina)
        self.assertNotIn("add-related", pagina)
        self.assertNotIn("change-related", pagina)
        self.assertNotIn("delete-related", pagina)


class FiltroRequisitoTest(BaseConLibreria):
    def test_schede_modello_filtrate_per_requisito(self):
        capo = User.objects.create_superuser("capo2", password="prova-prova-123")
        self.client.force_login(capo)
        scheda = SchedaModello.objects.first()
        url = reverse("admin:rischi_schedamodello_changelist")
        risposta = self.client.get(url, {"requisito__id__exact": scheda.requisito_id})
        self.assertContains(risposta, "Per requisito")
        self.assertEqual(
            risposta.context["cl"].result_count, SchedaModello.objects.filter(requisito=scheda.requisito).count()
        )


class SchedaModelloSezioniTest(BaseConLibreria):
    def test_sezioni_richiudibili_e_venti_norme(self):
        capo = User.objects.create_superuser("capo3", password="prova-prova-123")
        self.client.force_login(capo)
        scheda = SchedaModello.objects.first()
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[scheda.pk])).content.decode()
        self.assertEqual(pagina.count('<details class="sezione">'), 9)
        self.assertIn('name="norma_20"', pagina)
        self.assertIn("rischi/scheda.js", pagina)
        # le misure stanno dentro la sezione 6
        self.assertLess(pagina.index("6. RIDUZIONE DEL RISCHIO"), pagina.index('id="misure-group"'))
        self.assertLess(pagina.index('id="misure-group"'), pagina.index("7. STIMA FINALE"))
        nuova = self.client.get(reverse("admin:rischi_schedamodello_add")).content.decode()
        self.assertEqual(nuova.count('<details class="sezione" open>'), 9)


class TestoFormattatoTest(TestCase):
    """HTML dell'editor delle schede: incollato da Word, Google Documenti, pagine web."""

    def test_word(self):
        from .testo import in_reportlab

        word = (
            "<html xmlns:o='urn:schemas-microsoft-com:office:office'><head><style>p {margin:0}</style></head>"
            "<body><!--StartFragment--><p class=MsoNormal><b>Attenzione</b>: <span style='font-style:italic'>"
            "lame</span><o:p>&nbsp;</o:p></p><p class=MsoNormal>guanti</p><!--EndFragment--></body></html>"
        )
        self.assertEqual(in_reportlab(word), "<b>Attenzione</b>: <i>lame</i><br/>guanti")

    def test_google_documenti_e_stili(self):
        from .testo import in_reportlab

        html = (
            '<b style="font-weight:normal" id="docs-internal-guid-1"><p><span style="font-weight:700">'
            'Forte</span> <span style="text-decoration:underline">sotto</span> normale</p></b>'
        )
        self.assertEqual(in_reportlab(html), "<b>Forte</b> <u>sotto</u> normale")

    def test_righe_vuote_ed_elenchi_annidati(self):
        from .testo import in_reportlab, semplice

        html = "<div>a</div><div><br></div><div>b<br></div><ol><li>uno<ul><li>sotto</li></ul></li></ol>"
        self.assertEqual(
            in_reportlab(html), "a<br/><br/>b<br/>1. uno<br/>&nbsp;&nbsp;&nbsp;&nbsp;• sotto"
        )
        self.assertEqual(semplice(html), "a\n\nb\n1. uno\n  • sotto")
        self.assertEqual(semplice("solo **testo**"), "solo testo")

    def test_codice_scartato(self):
        from .testo import in_reportlab

        self.assertEqual(in_reportlab('<p>ok<script>alert(1)</script><img src=x onerror="x"></p>'), "ok")


class StaticiAggiornatiTest(BaseConLibreria):
    def test_css_e_script_con_data_di_modifica(self):
        self.client.force_login(User.objects.create_superuser("capo", "capo@example.com", "x"))
        scheda = SchedaModello.objects.first()
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[scheda.pk])).content.decode()
        self.assertRegex(pagina, r"rischi/admin_scheda\.css\?v=\d+")
        self.assertRegex(pagina, r"rischi/scheda\.js\?v=\d+")


class RequisitiAllegatoIIITest(BaseConLibreria):
    def test_titoli_e_testi_del_regolamento(self):
        from .models import RequisitoRESS

        requisito = RequisitoRESS.objects.get(codice="1.1.1")
        self.assertEqual(requisito.titolo, "Applicabilità")
        self.assertIn("quasi-macchine", requisito.descrizione)
        self.assertEqual(RequisitoRESS.objects.get(codice="1.2.4.1").titolo, "Arresto normale")
        # 1.7.4.3 della Direttiva è 1.7.5 nel Regolamento
        self.assertFalse(RequisitoRESS.objects.filter(codice="1.7.4.3").exists())
        self.assertEqual(RequisitoRESS.objects.get(codice="1.7.5").titolo, "Pubblicazioni illustrative o promozionali")
        # Il testo introduttivo di 1.7.4 compare nei suoi sottopunti
        self.assertIn("1.7.4. Istruzioni per l'uso", RequisitoRESS.objects.get(codice="1.7.4.2").descrizione)
        codici = list(RequisitoRESS.objects.values_list("codice", flat=True))
        self.assertEqual(codici.index("1.5.9") + 1, codici.index("1.5.10"))

    def test_note_del_requisito_nella_scheda_modello_e_nel_pdf(self):
        from . import documenti

        utente = User.objects.create_superuser("capo", "capo@example.com", "x")
        self.client.force_login(utente)
        modello = SchedaModello.objects.filter(requisito__codice="1.1.5").first()
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[modello.pk])).content.decode()
        self.assertIn("note-requisito", pagina)
        self.assertIn("movimentati e trasportati in modo sicuro", pagina)
        self.assertNotIn('name="scheda_originale"', pagina)

        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        rev = analisi.revisione_corrente
        scheda = rev.schede.get(requisito__codice="1.1.5")
        scheda.stampa_note_requisito = False  # attivo di default: spento non si stampa
        scheda.save()
        self.assertNotIn("movimentati e trasportati", DocumentiTest.leggi(documenti.valutazione(rev)))
        scheda.stampa_note_requisito = True
        scheda.save()
        testo = DocumentiTest.leggi(documenti.valutazione(rev))
        self.assertIn("Requisito 1.1.5 – testo del Regolamento", testo)
        self.assertIn("movimentati e trasportati in modo sicuro", testo)


class NormeDeiPericoliTest(BaseConLibreria):
    def test_norme_del_pericolo_nell_area_norme_della_scheda(self):
        from . import documenti
        from .models import Norma, Pericolo

        utente = User.objects.create_superuser("capo", "capo@example.com", "x")
        self.client.force_login(utente)
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        scheda = analisi.revisione_corrente.schede.filter(pericoli__isnull=False).first()
        pericolo = scheda.pericoli.first()
        norma = Norma.objects.create(codice="EN 99999", titolo="Norma del pericolo di prova")
        url = reverse("admin:rischi_pericolo_change", args=[pericolo.pk])
        self.assertContains(self.client.get(url), 'name="norma_10"')
        self.client.post(url, {"codice": pericolo.codice, "descrizione": pericolo.descrizione, "norma_1": norma.pk})
        self.assertEqual(list(pericolo.norme.all()), [norma])
        testo = DocumentiTest.leggi(documenti.valutazione(analisi.revisione_corrente))
        self.assertIn("EN 99999", testo)
        self.assertIn("Norma del pericolo di prova", testo)

    def test_misure_della_scheda_modello_senza_norma(self):
        utente = User.objects.create_superuser("capo", "capo@example.com", "x")
        self.client.force_login(utente)
        modello = SchedaModello.objects.filter(misure__isnull=False).first()
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[modello.pk])).content.decode()
        self.assertIn('name="misure-0-testo"', pagina)
        self.assertNotIn('name="misure-0-norma"', pagina)
        self.assertNotIn('name="misure-0-ordine"', pagina)
        self.assertIn('Misura <span class="numero-misura">1</span>', pagina)


class SoluzioniENormeGeneraliTest(BaseConLibreria):
    def test_norme_delle_soluzioni_nella_scheda_e_nella_dichiarazione(self):
        from . import documenti
        from .forms import MisureFormSet
        from .models import Norma, SoluzioneProtezione

        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        scheda = analisi.revisione_corrente.schede.first()
        norma = Norma.objects.create(codice="EN 88888", titolo="Norma della soluzione", armonizzata=True)
        soluzione = SoluzioneProtezione.objects.create(
            nome="Riparo di prova", tipo="PROT", testo="Testo proposto della soluzione"
        )
        soluzione.norme.set([norma])
        # Scelta la soluzione e lasciato vuoto il testo, la misura prende tipo e testo della soluzione.
        prima = scheda.misure.count()
        dati = {
            "misure-TOTAL_FORMS": str(prima + 1), "misure-INITIAL_FORMS": str(prima),
            "misure-MIN_NUM_FORMS": "0", "misure-MAX_NUM_FORMS": "1000",
        }
        for i, misura in enumerate(scheda.misure.all()):
            dati.update({f"misure-{i}-id": misura.pk, f"misure-{i}-ordine": misura.ordine,
                         f"misure-{i}-tipo": misura.tipo, f"misure-{i}-testo": misura.testo})
        dati.update({f"misure-{prima}-ordine": "9", f"misure-{prima}-tipo": "DACL",
                     f"misure-{prima}-soluzione": soluzione.pk, f"misure-{prima}-testo": ""})
        formset = MisureFormSet(dati, instance=scheda, prefix="misure")
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        nuova = scheda.misure.get(soluzione=soluzione)
        self.assertEqual((nuova.tipo, nuova.testo), ("PROT", "Testo proposto della soluzione"))
        self.assertIn(norma, scheda.norme_collegate())

        testo = DocumentiTest.leggi(documenti.valutazione(analisi.revisione_corrente))
        self.assertIn("EN 88888", testo)
        armonizzate, _ = documenti.norme_applicate(analisi.revisione_corrente)
        self.assertIn(norma, armonizzate)

    def test_norma_di_tipo_c_e_norme_sempre_applicate(self):
        from . import documenti
        from .models import Norma

        macchina = self.nuova_macchina()
        analisi = servizi.crea_analisi_da_libreria(macchina, self.compilatore)
        tipo_c, _ = Norma.objects.update_or_create(
            codice="EN ISO 16089", defaults={"titolo": "Rettificatrici fisse", "tipo": "C", "armonizzata": True}
        )
        tipo_a, _ = Norma.objects.update_or_create(
            codice="EN ISO 12100", defaults={"titolo": "Principi generali", "tipo": "A", "sempre_applicata": True}
        )
        macchina.norme_tipo_c.set([tipo_c])
        revisione = analisi.revisione_corrente
        self.assertEqual(documenti.norme_generali(revisione), [tipo_a, tipo_c])
        armonizzate, altre = documenti.norme_applicate(revisione)
        self.assertIn(tipo_c, armonizzate)
        self.assertIn(tipo_a, armonizzate + altre)
        testo = DocumentiTest.leggi(documenti.valutazione(revisione))
        self.assertIn("Norme di riferimento dell'analisi", testo)
        self.assertIn("EN ISO 16089", testo)

        utente = User.objects.create_superuser("capo", "capo@example.com", "x")
        self.client.force_login(utente)
        pagina = self.client.get(reverse("macchina", args=[macchina.pk])).content.decode()
        self.assertIn('name="norme_tipo_c"', pagina)
        self.assertNotIn(f'name="norme_tipo_c" value="{tipo_a.pk}"', pagina)


class NormeAutomaticheTest(BaseConLibreria):
    def test_norme_da_requisito_e_da_parole_chiave_con_esclusione(self):
        from . import documenti
        from .models import MisuraAnalisi, Norma, SoluzioneProtezione

        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        scheda = analisi.revisione_corrente.schede.first()
        del_requisito = Norma.objects.create(codice="EN 70001", titolo="Norma del requisito")
        della_soluzione = Norma.objects.create(codice="EN 70002", titolo="Norma della soluzione")
        scheda.requisito.norme.add(del_requisito)
        soluzione = SoluzioneProtezione.objects.create(nome="Prova interblocco", parole_chiave="porta di prova")
        soluzione.norme.set([della_soluzione])
        MisuraAnalisi.objects.create(scheda=scheda, ordine=99, tipo="PROT", testo="Una <b>porta di prova</b> chiusa.")

        origini = scheda.origini_norme()
        self.assertEqual(origini[del_requisito], [f"RESS {scheda.requisito.codice}"])
        self.assertTrue(origini[della_soluzione][0].startswith("misura "))
        self.assertIn(della_soluzione, scheda.norme_collegate())

        # Il tecnico toglie la spunta alla norma della soluzione: resta solo quella del requisito.
        self.client.force_login(self.compilatore)
        pagina = self.client.get(reverse("scheda", args=[scheda.pk]))
        self.assertContains(pagina, "Norme ricavate in automatico")
        form = pagina.context["form"]
        self.assertIn(str(della_soluzione.pk), form.initial["norme_automatiche"])
        dati = {}
        for nome in form.fields:
            valore = form.initial.get(nome)
            if hasattr(valore, "__iter__") and not isinstance(valore, str):
                dati[nome] = [getattr(v, "pk", v) for v in valore]
            elif valore is not None:
                dati[nome] = getattr(valore, "pk", valore)
        dati["norme_automatiche"] = [n.pk for n in origini if n != della_soluzione]
        misure = pagina.context["misure"]
        dati.update({f"misure-{k}": v for k, v in misure.management_form.initial.items()})
        dati["misure-TOTAL_FORMS"] = misure.initial_form_count()
        for i, mf in enumerate(misure.forms):
            if mf.instance.pk:
                dati.update({f"misure-{i}-id": mf.instance.pk, f"misure-{i}-ordine": mf.instance.ordine,
                             f"misure-{i}-tipo": mf.instance.tipo, f"misure-{i}-testo": mf.instance.testo})
        risposta = self.client.post(reverse("scheda", args=[scheda.pk]), dati)
        self.assertEqual(risposta.status_code, 302)
        self.assertEqual(list(scheda.norme_escluse.all()), [della_soluzione])
        self.assertNotIn(della_soluzione, scheda.norme_collegate())
        self.assertIn(del_requisito, scheda.norme_collegate())
        testo = DocumentiTest.leggi(documenti.valutazione(analisi.revisione_corrente))
        self.assertIn("EN 70001", testo)
        self.assertNotIn("EN 70002", testo)


class SintesiNormeTest(BaseConLibreria):
    def test_ogni_norma_della_libreria_ha_la_sintesi(self):
        from .dati.sintesi_norme import SINTESI
        from .models import Norma

        for norma in Norma.objects.filter(codice__in=SINTESI):
            self.assertTrue(norma.nota.startswith(SINTESI[norma.codice]), (norma.codice, norma.nota[:200]))


class CapitoliValutazioneTest(BaseConLibreria):
    def test_capitoli_modificabili_nella_valutazione(self):
        from . import documenti
        from .models import CapitoloValutazione

        self.assertEqual(
            list(CapitoloValutazione.objects.values_list("titolo", flat=True)), ["Definizioni", "Principi generali"]
        )
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        testo = DocumentiTest.leggi(documenti.valutazione(analisi.revisione_corrente))
        self.assertIn("zona pericolosa", testo)
        self.assertIn("Principi generali", testo)
        principi = CapitoloValutazione.objects.get(titolo="Principi generali")
        principi.testo = "<b>Testo</b> scritto dal tecnico."
        principi.save()
        CapitoloValutazione.objects.filter(titolo="Definizioni").update(attivo=False)
        testo = DocumentiTest.leggi(documenti.valutazione(analisi.revisione_corrente))
        self.assertIn("Testo scritto dal tecnico.", testo)
        self.assertNotIn("persona esposta»", testo)

        utente = User.objects.create_superuser("capo", "capo@example.com", "x")
        self.client.force_login(utente)
        self.assertContains(self.client.get(reverse("admin:rischi_capitolovalutazione_changelist")), "Principi generali")


class ImmaginiAllegateTest(BaseConLibreria):
    def setUp(self):
        import tempfile

        from django.test import override_settings

        self.media = tempfile.TemporaryDirectory()
        self.impostazioni = override_settings(MEDIA_ROOT=self.media.name)
        self.impostazioni.enable()

    def tearDown(self):
        self.impostazioni.disable()
        self.media.cleanup()

    @staticmethod
    def png():
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (400, 200), "red").save(buffer, "PNG")
        return buffer.getvalue()

    @staticmethod
    def pdf(testo):
        from reportlab.pdfgen.canvas import Canvas

        buffer = io.BytesIO()
        tela = Canvas(buffer)
        tela.drawString(100, 700, testo)
        tela.save()
        return buffer.getvalue()

    def test_allegati_dal_modello_alla_valutazione(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from . import documenti
        from .models import AllegatoAnalisi, AllegatoModello

        prima = servizi.crea_analisi_da_libreria(self.nuova_macchina("25-19"), self.compilatore)
        modello = prima.revisione_corrente.schede.exclude(decisione=SchedaAnalisi.Decisione.SCARTATA)[0].origine
        capo = User.objects.create_superuser("capo9", password="prova-prova-123")
        self.client.force_login(capo)
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[modello.pk])).content.decode()
        self.assertIn("9. IMMAGINI ALLEGATE", pagina)
        self.assertLess(pagina.index("9. IMMAGINI ALLEGATE"), pagina.index('id="allegati-group"'))

        AllegatoModello.objects.create(
            scheda=modello, file=SimpleUploadedFile("protezione.png", self.png()), testo="Riparo <b>frontale</b>", allineamento="SX", posizione_testo="DX", ordine=1
        )
        AllegatoModello.objects.create(
            scheda=modello, file=SimpleUploadedFile("schema.pdf", self.pdf("Schema elettrico allegato")), ordine=2
        )
        # Un file che non è immagine né PDF non si carica.
        with self.assertRaises(ValidationError):
            AllegatoModello(scheda=modello, file=SimpleUploadedFile("testo.txt", b"x")).full_clean()

        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        scheda = analisi.revisione_corrente.schede.get(origine=modello)
        self.assertEqual([a.nome_file for a in scheda.allegati.all()], ["protezione.png", "schema.pdf"])
        self.assertEqual(scheda.allegati.first().posizione_testo, "DX")

        # Nella commessa il tecnico aggiunge e toglie immagini dalla scheda.
        self.client.force_login(self.compilatore)
        pagina = self.client.get(reverse("scheda", args=[scheda.pk])).content.decode()
        self.assertIn("9. IMMAGINI ALLEGATE", pagina)
        # "Salva scheda" sta accanto ad "Aggiorna dalla scheda modello" e invia il modulo della scheda
        self.assertIn('form="form-scheda">Salva scheda</button>', pagina)
        self.assertLess(pagina.index("Salva scheda"), pagina.index("Aggiorna dalla scheda modello"))
        risposta = self.client.post(
            reverse("aggiungi_allegato", args=[scheda.pk]),
            {"file": SimpleUploadedFile("foto.png", self.png()), "testo": "Foto della zona", "allineamento": "DX", "posizione_testo": "SOPRA"},
        )
        self.assertEqual(risposta.status_code, 302)
        aggiunto = scheda.allegati.get(testo="Foto della zona")
        self.assertEqual(aggiunto.ordine, 3)
        self.assertEqual((aggiunto.allineamento, aggiunto.posizione_testo), ("DX", "SOPRA"))

        valutazione = documenti.valutazione(analisi.revisione_corrente)
        testo = DocumentiTest.leggi(valutazione)
        self.assertIn("9. IMMAGINI ALLEGATE", testo)
        self.assertIn("Riparo frontale", testo)
        self.assertIn("Foto della zona", testo)
        self.assertIn("PDF allegato in appendice: schema.pdf", testo)
        self.assertIn("Schema elettrico allegato", testo)  # pagina del PDF aggiunta in fondo

        self.client.post(reverse("elimina_allegato", args=[aggiunto.pk]))
        self.assertFalse(AllegatoAnalisi.objects.filter(pk=aggiunto.pk).exists())


class ConsiderazioniPrecompilateTest(BaseConLibreria):
    def test_riempie_solo_i_campi_vuoti_con_lo_stesso_requisito(self):
        import importlib
        import json

        from django.apps import apps

        from .models import RequisitoRESS

        carica = importlib.import_module("rischi.migrations.0033_considerazioni_schede_modello").carica
        dati = json.loads((Path(settings.BASE_DIR) / "rischi" / "dati" / "considerazioni_schede.json").read_text("utf-8"))
        self.assertEqual(len(dati), 78)
        voce = dati["TAV-01"]
        requisito = RequisitoRESS.objects.get(riferimento=self.riferimento, codice=voce["requisito"])
        altro = RequisitoRESS.objects.exclude(pk=requisito.pk).first()
        modulo = Modulo.objects.first()
        SchedaModello.objects.filter(codice__in=["TAV-01", "TAV-02"]).delete()
        scritta = SchedaModello.objects.create(
            codice="TAV-01", modulo=modulo, requisito=requisito, considerazioni_pericoli="Scritto dal tecnico."
        )
        diversa = SchedaModello.objects.create(codice="TAV-02", modulo=modulo, requisito=altro)
        carica(apps, None)
        scritta.refresh_from_db()
        diversa.refresh_from_db()
        self.assertEqual(scritta.considerazioni_pericoli, "Scritto dal tecnico.")
        self.assertEqual(scritta.considerazioni_stima_iniziale, voce["campi"]["considerazioni_stima_iniziale"])
        self.assertEqual(diversa.considerazioni_stima_iniziale, "")


class NuoviModuliTest(BaseConLibreria):
    def test_moduli_rinominati_schede_spostate_e_nuove_in_bozza(self):
        import importlib

        from django.apps import apps

        from .models import RequisitoRESS

        applica = importlib.import_module("rischi.migrations.0034_nuovi_moduli").applica
        luc = Modulo.objects.create(nome="Unità di lucidatura CNC (prova)", sigla="LUC", ordine=50)
        rob = Modulo.objects.create(nome="Gruppo robot (prova)", sigla="ROB", ordine=51)
        requisito = RequisitoRESS.objects.get(riferimento=self.riferimento, codice="1.3.8.1")
        lucidatura = SchedaModello.objects.create(codice="LUC-01", modulo=luc, requisito=requisito)
        nastro = SchedaModello.objects.create(codice="ROB-02", modulo=rob, requisito=requisito)
        macchina = self.nuova_macchina()
        macchina.moduli.add(rob)

        applica(apps, None)

        lucidatura.refresh_from_db()
        nastro.refresh_from_db()
        self.assertEqual((lucidatura.codice, lucidatura.modulo.sigla), ("PUC-01", "PUC"))
        self.assertEqual((nastro.codice, nastro.modulo.sigla), ("SMC-01", "SMC"))
        self.assertIn("SMC", set(macchina.moduli.values_list("sigla", flat=True)))
        nuove = SchedaModello.objects.filter(modulo__sigla="MAN")
        self.assertEqual(nuove.count(), 8)
        self.assertTrue(all(s.stato == "BOZZA" and s.misure.exists() and s.considerazioni_stima_iniziale for s in nuove))
        # Il codice lasciato libero dalla scheda spostata non si riusa
        self.assertFalse(SchedaModello.objects.filter(codice="ROB-02").exists())
        # Una seconda esecuzione non duplica le schede nuove
        applica(apps, None)
        self.assertEqual(SchedaModello.objects.filter(modulo__sigla="MAN").count(), 8)


class RitocchiLibreriaTest(BaseConLibreria):
    def setUp(self):
        super().setUp()
        self.client.force_login(User.objects.create_superuser("capo", "capo@example.com", "x"))

    def test_elenco_libreria_senza_aggiungi_e_modifica(self):
        pagina = self.client.get(reverse("admin:index")).content.decode()
        self.assertIn(reverse("admin:rischi_schedamodello_changelist"), pagina)
        self.assertNotIn('class="addlink"', pagina)
        self.assertNotIn('class="changelink"', pagina)

    def test_frecce_spostano_e_rinumerano(self):
        from .models import CondizioneOperativa

        nomi = list(CondizioneOperativa.objects.values_list("nome", flat=True))
        self.assertGreater(len(nomi), 2)
        elenco = self.client.get(reverse("admin:rischi_condizioneoperativa_changelist")).content.decode()
        self.assertIn("Sposta in giù", elenco)
        self.assertNotIn('name="form-0-ordine"', elenco)
        primo = CondizioneOperativa.objects.get(nome=nomi[0])
        self.client.post(reverse("admin:rischi_condizioneoperativa_sposta", args=[primo.pk, "giu"]))
        self.assertEqual(list(CondizioneOperativa.objects.values_list("nome", flat=True)), [nomi[1], nomi[0], *nomi[2:]])
        self.assertEqual(list(CondizioneOperativa.objects.values_list("ordine", flat=True)),
                         [10 * i for i in range(1, len(nomi) + 1)])
        # In cima non si sale oltre; la voce nuova va in fondo
        self.client.post(reverse("admin:rischi_condizioneoperativa_sposta", args=[CondizioneOperativa.objects.first().pk, "su"]))
        self.assertEqual(CondizioneOperativa.objects.first().nome, nomi[1])
        self.client.post(reverse("admin:rischi_condizioneoperativa_add"), {"nome": "Condizione nuova"})
        self.assertEqual(CondizioneOperativa.objects.last().nome, "Condizione nuova")
        # Con GET non cambia nulla
        self.client.get(reverse("admin:rischi_condizioneoperativa_sposta", args=[primo.pk, "giu"]))
        self.assertEqual(CondizioneOperativa.objects.first().nome, nomi[1])

    def test_note_requisito_stampate_e_note_vuote(self):
        import importlib

        from django.apps import apps

        scheda = SchedaModello.objects.first()
        SchedaModello.objects.filter(pk=scheda.pk).update(stampa_note_requisito=False, note="Vecchia nota")
        importlib.import_module("rischi.migrations.0035_note_requisito_e_note_vuote").applica(apps, None)
        scheda.refresh_from_db()
        self.assertEqual((scheda.stampa_note_requisito, scheda.note), (True, ""))
        self.assertTrue(SchedaModello(modulo=scheda.modulo, requisito=scheda.requisito).stampa_note_requisito)

    def test_pericoli_a_caselle_per_gruppo(self):
        scheda = SchedaModello.objects.filter(pericoli__isnull=False).first()
        pagina = self.client.get(reverse("admin:rischi_schedamodello_change", args=[scheda.pk])).content.decode()
        self.assertIn('class="scelta-pericoli"', pagina)
        self.assertIn("1. Pericoli meccanici", pagina)
        self.assertIn(f'name="pericoli" value="{scheda.pericoli.first().pk}"', pagina)
        self.assertNotIn("SelectFilter", pagina)


class FunzioniSicurezzaTest(BaseConLibreria):
    """Funzioni di sicurezza (EN ISO 13849-1) nella revisione: collegate alle misure, bloccate e copiate con essa."""

    def setUp(self):
        from .models import FunzioneSicurezza, MisuraAnalisi, ValutazioneFunzione

        self.analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.rev = self.analisi.revisione_corrente
        self.scheda = self.rev.schede.filter(origine__isnull=False, misure__isnull=False).first()
        self.misura = MisuraAnalisi.objects.create(
            scheda=self.scheda, ordine=99, tipo="PROT", testo="Riparo interbloccato sulla porta di carico"
        )
        self.funzione = FunzioneSicurezza.objects.create(
            revisione=self.rev, nome="Apertura porta di carico", s="S2", f="F2", p="P1"
        )
        self.funzione.misure.add(self.misura)
        self.valutazione = ValutazioneFunzione.objects.create(
            funzione=self.funzione, dettaglio={"sottosistemi": [{"nome": "Interruttore"}], "validazione": {"esiti": {}}},
            pl="d", pfh=42.9, esito=True,
        )

    def approva(self, rev):
        servizi.invia_in_verifica(rev, self.compilatore)
        servizi.segna_verificata(rev, self.verificatore)
        servizi.approva(rev, self.approvatore)

    def test_plr_dal_grafo_del_rischio(self):
        from .models import plr

        attesi = {
            ("S1", "F1", "P1"): "a", ("S1", "F1", "P2"): "b", ("S1", "F2", "P1"): "b", ("S1", "F2", "P2"): "c",
            ("S2", "F1", "P1"): "c", ("S2", "F1", "P2"): "d", ("S2", "F2", "P1"): "d", ("S2", "F2", "P2"): "e",
        }
        for parametri, atteso in attesi.items():
            self.assertEqual(plr(*parametri), atteso, parametri)
        self.assertEqual(plr("S2", "", "P1"), "")
        self.assertEqual(self.funzione.plr, "d")

    def test_funzione_anche_senza_misura(self):
        from .models import FunzioneSicurezza

        emergenza = FunzioneSicurezza.objects.create(revisione=self.rev, nome="Arresto di emergenza generale")
        self.assertEqual(emergenza.plr, "")
        self.assertFalse(emergenza.misure.exists())
        self.assertEqual(list(self.misura.funzioni.all()), [self.funzione])

    def test_bloccata_con_la_revisione(self):
        self.approva(self.rev)
        self.funzione.refresh_from_db()
        with self.assertRaises(RevisioneBloccata):
            self.funzione.save()
        with self.assertRaises(RevisioneBloccata):
            self.funzione.misure.clear()
        with self.assertRaises(RevisioneBloccata):
            self.valutazione.save()

    def test_nuova_revisione_copia_funzioni_e_valutazioni(self):
        self.approva(self.rev)
        rev1 = servizi.nuova_revisione(self.analisi, self.compilatore, "Aggiunta porta")
        funzione = rev1.funzioni.get()
        self.assertEqual((funzione.nome, funzione.plr), ("Apertura porta di carico", "d"))
        misura = funzione.misure.get()
        self.assertEqual(misura.scheda.revisione, rev1)
        self.assertEqual(misura.testo, self.misura.testo)
        self.assertEqual(funzione.valutazione.dettaglio, self.valutazione.dettaglio)
        # La revisione approvata resta com'era
        self.assertEqual(list(self.rev.funzioni.get().misure.all()), [self.misura])

    def test_copia_su_altra_macchina_senza_validazione(self):
        self.approva(self.rev)
        copia = servizi.crea_analisi_da_copia(self.nuova_macchina("26-04"), self.rev, self.compilatore)
        funzione = copia.revisione_corrente.funzioni.get()
        self.assertEqual(funzione.misure.get().scheda.revisione, copia.revisione_corrente)
        self.assertNotIn("validazione", funzione.valutazione.dettaglio)
        self.assertEqual(funzione.valutazione.pl, "d")

    def test_aggiorna_da_modello_tiene_il_collegamento(self):
        misura = self.scheda.misure.exclude(pk=self.misura.pk).first()
        self.funzione.misure.set([misura])
        servizi.aggiorna_da_modello(self.scheda, self.compilatore)
        nuova = self.funzione.misure.get()
        self.assertEqual(nuova.scheda, self.scheda)
        self.assertEqual(nuova.testo, misura.testo)

    def test_registro_con_impronta_del_dettaglio(self):
        with utente_attivo(self.compilatore):
            self.valutazione.dettaglio = {"sottosistemi": []}
            self.valutazione.save()
        voce = RegistroModifica.objects.filter(
            tabella="valutazione della funzione", azione=RegistroModifica.Azione.MODIFICA
        ).get()
        prima, dopo = voce.modifiche["dettaglio"]
        self.assertTrue(prima.startswith("JSON ") and dopo.startswith("JSON "))
        self.assertNotEqual(prima, dopo)

    def test_elimina_commessa_con_funzioni(self):
        from .models import FunzioneSicurezza, ValutazioneFunzione

        servizi.elimina_commessa(self.analisi.macchina.commessa, self.compilatore)
        self.assertFalse(FunzioneSicurezza.objects.exists())
        self.assertFalse(ValutazioneFunzione.objects.exists())


class ArticoliSicurezzaTest(TestCase):
    """Import dell'archivio articoli della safety evaluation nella libreria."""

    ARCHIVIO = [
        {"id": "s120-smm", "codice": "S120 SMM booksize", "descrizione": "Motor Module singolo", "produttore": "Siemens",
         "tipo": "attuatore", "pfh": 10, "b10d": None, "mttfd": None, "plMax": None, "fonte": "Entry-ID 76254308",
         "dataFonte": "2024-04", "verificato": True, "note": "Confrontato con il PDF", "utilizzato": "2026-10-01"},
        {"id": "pizzato-1", "codice": "FR 693", "descrizione": "Interruttore", "produttore": "Pizzato", "tipo": "sensore",
         "pfh": None, "b10d": 2000000, "mttfd": None, "plMax": None, "fonte": "SISTEMA A26", "verificato": False,
         "libreria": "A26", "gruppo": "FR"},
    ]

    def importa(self, dati):
        import json
        import tempfile

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump(dati, f)
        uscita = io.StringIO()
        call_command("importa_articoli", f.name, stdout=uscita)
        Path(f.name).unlink()
        return uscita.getvalue()

    def test_import_e_reimport(self):
        import datetime

        from .models import ArticoloSicurezza

        self.assertIn("2 nuovi", self.importa(self.ARCHIVIO))
        smm = ArticoloSicurezza.objects.get(chiave="s120-smm")
        self.assertEqual((smm.pfh, smm.verificato, smm.utilizzato), (10, True, datetime.date(2026, 10, 1)))
        self.assertEqual(ArticoloSicurezza.objects.get(chiave="pizzato-1").b10d, 2000000)
        self.assertIn("2 invariati", self.importa(self.ARCHIVIO))

        # Un valore cambiato rimette l'articolo da verificare; le note restano, l'ultimo utilizzo è il più recente
        cambiato = [{**self.ARCHIVIO[0], "pfh": 14, "note": "", "utilizzato": "2026-09-01"}]
        self.assertIn("1 aggiornati", self.importa({"articoli": cambiato}))
        smm.refresh_from_db()
        self.assertEqual((smm.pfh, smm.verificato, smm.note), (14, False, "Confrontato con il PDF"))
        self.assertEqual(smm.utilizzato, datetime.date(2026, 10, 1))

    def test_file_non_valido(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            self.importa([{"codice": "senza id"}])

    def test_elenco_in_libreria(self):
        self.importa(self.ARCHIVIO)
        capo = User.objects.create_superuser("capo", password="prova-prova-123")
        self.client.force_login(capo)
        pagina = self.client.get(reverse("admin:rischi_articolosicurezza_changelist") + "?verificato__exact=0")
        self.assertContains(pagina, "FR 693")
        self.assertNotContains(pagina, "S120 SMM booksize")


class PagineFunzioniTest(BaseConLibreria):
    """Fase 2: la funzione di sicurezza si crea dalla misura della scheda o a mano dalla pagina dell'analisi."""

    def setUp(self):
        from .models import MisuraAnalisi

        self.analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.rev = self.analisi.revisione_corrente
        self.scheda = self.rev.schede.first()
        self.misura = MisuraAnalisi.objects.create(
            scheda=self.scheda, ordine=99, tipo="PROT", testo="Riparo interbloccato sulla porta di carico"
        )

    def test_crea_dalla_misura_della_scheda(self):
        self.client.force_login(self.compilatore)
        url = f"{reverse('nuova_funzione', args=[self.rev.pk])}?misura={self.misura.pk}"
        self.assertContains(self.client.get(reverse("scheda", args=[self.scheda.pk])), url.replace("&", "&amp;"))
        pagina = self.client.get(url)
        self.assertRegex(pagina.content.decode(), rf'value="{self.misura.pk}" id="id_misure_\d+" checked')
        risposta = self.client.post(url, {
            "nome": "Apertura porta di carico", "descrizione": "Apertura porta → STO", "s": "S2", "f": "F1", "p": "P2",
            "misure": [self.misura.pk],
        })
        self.assertRedirects(risposta, reverse("analisi", args=[self.analisi.pk]) + "#funzioni")
        funzione = self.rev.funzioni.get()
        self.assertEqual((funzione.plr, list(funzione.misure.all())), ("d", [self.misura]))
        analisi = self.client.get(reverse("analisi", args=[self.analisi.pk]))
        self.assertContains(analisi, "Apertura porta di carico")
        self.assertContains(self.client.get(reverse("scheda", args=[self.scheda.pk])), "(PLr d)")

    def test_a_mano_e_controllo_plr(self):
        self.client.force_login(self.compilatore)
        self.client.post(reverse("nuova_funzione", args=[self.rev.pk]), {"nome": "Arresto di emergenza generale"})
        funzione = self.rev.funzioni.get()
        self.assertFalse(funzione.misure.exists())
        self.assertIn("funzione", {a.tipo for a in servizi.controlli(self.rev)})
        self.client.post(reverse("funzione", args=[funzione.pk]), {
            "nome": "Arresto di emergenza generale", "s": "S2", "f": "F2", "p": "P1",
        })
        funzione.refresh_from_db()
        self.assertEqual(funzione.plr, "d")
        self.assertNotIn("funzione", {a.tipo for a in servizi.controlli(self.rev)})

    def test_misure_solo_della_stessa_revisione(self):
        from .models import MisuraAnalisi

        altra = servizi.crea_analisi_da_libreria(self.nuova_macchina("26-05"), self.compilatore)
        estranea = MisuraAnalisi.objects.create(
            scheda=altra.revisione_corrente.schede.first(), tipo="PROT", testo="Misura di un'altra commessa"
        )
        informazione = MisuraAnalisi.objects.create(scheda=self.scheda, tipo="INFO", testo="Cartello")
        self.client.force_login(self.compilatore)
        pagina = self.client.get(reverse("nuova_funzione", args=[self.rev.pk]))
        self.assertContains(pagina, "Riparo interbloccato")
        self.assertNotContains(pagina, "Misura di un&#x27;altra commessa")
        self.assertNotContains(pagina, "Cartello")
        risposta = self.client.post(reverse("nuova_funzione", args=[self.rev.pk]), {
            "nome": "Prova", "misure": [estranea.pk, informazione.pk],
        })
        self.assertEqual(risposta.status_code, 200)
        self.assertFalse(self.rev.funzioni.exists())

    def test_sola_lettura_e_eliminazione(self):
        from .models import FunzioneSicurezza

        funzione = FunzioneSicurezza.objects.create(revisione=self.rev, nome="Barriera", s="S1", f="F1", p="P1")
        self.client.force_login(self.verificatore)
        self.assertContains(self.client.get(reverse("funzione", args=[funzione.pk])), "Sola lettura")
        self.assertEqual(self.client.post(reverse("elimina_funzione", args=[funzione.pk])).status_code, 403)
        self.client.force_login(self.compilatore)
        self.client.post(reverse("elimina_funzione", args=[funzione.pk]))
        self.assertFalse(FunzioneSicurezza.objects.exists())


class CalcoloPLTest(BaseConLibreria):
    """Fase 3: calcolo del PL nella pagina della funzione, ricalcolato dal server con engine.js."""

    def setUp(self):
        from .models import ArticoloSicurezza, FunzioneSicurezza

        self.analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.rev = self.analisi.revisione_corrente
        self.funzione = FunzioneSicurezza.objects.create(revisione=self.rev, nome="Porta", s="S2", f="F1", p="P2")
        for chiave, tipo in (("fdi", "sensore"), ("fcpu", "logica"), ("sto", "attuatore")):
            ArticoloSicurezza.objects.create(chiave=chiave, codice=chiave.upper(), tipo=tipo, pfh=10, fonte="Certificato")
        blocco = lambda ruolo, chiave: {
            "id": chiave, "nome": chiave, "ruolo": ruolo, "percorso": "", "metodo": "pfh", "categoria": None,
            "componenti": [{"articoloId": chiave, "qty": 1}], "ccf": {}, "pfhK1": None,
        }
        self.dettaglio = {"sottosistemi": [
            blocco("rilevamento", "fdi"), blocco("logica", "fcpu"), blocco("attuazione", "sto"),
        ]}
        self.url = reverse("valutazione_funzione", args=[self.funzione.pk])

    def salva(self, dettaglio, risultato=None, utente=None):
        import json

        self.client.force_login(utente or self.compilatore)
        return self.client.post(
            self.url, json.dumps({"dettaglio": dettaglio, "risultato": risultato or {}}), content_type="application/json"
        )

    def test_pagina_e_articoli(self):
        self.client.force_login(self.compilatore)
        pagina = self.client.get(self.url)
        self.assertContains(pagina, 'id="dati-valutazione"')
        self.assertContains(pagina, "rischi/safety/engine.js")
        articoli = self.client.get(reverse("articoli_sicurezza")).json()["articoli"]
        self.assertEqual({a["id"] for a in articoli}, {"fdi", "fcpu", "sto"})
        self.assertEqual(articoli[0]["pfh"], 10)

    def test_salva_e_ricalcola_sul_server(self):
        import datetime

        from .models import ArticoloSicurezza

        # Il risultato inviato dalla pagina non conta: il server ricalcola con engine.js
        risposta = self.salva(self.dettaglio, {"pl": "a", "pfh": 1, "ok": False})
        self.assertEqual(risposta.status_code, 200, risposta.content)
        self.assertIn("ricalcolata dal server", risposta.json()["messaggio"])
        valutazione = self.funzione.valutazione
        self.assertEqual((valutazione.pl, valutazione.pfh, valutazione.esito), ("e", 30, True))
        self.assertEqual(ArticoloSicurezza.objects.get(chiave="sto").utilizzato, datetime.date.today())
        # Le parti del dettaglio che la pagina non gestisce restano
        valutazione.dettaglio["validazione"] = {"esiti": {"funz:": "OK"}}
        valutazione.save()
        self.salva(self.dettaglio)
        valutazione.refresh_from_db()
        self.assertEqual(valutazione.dettaglio["validazione"], {"esiti": {"funz:": "OK"}})

    def test_incompleta_non_soddisfa(self):
        self.salva({"sottosistemi": self.dettaglio["sottosistemi"][:2]})
        self.assertFalse(self.funzione.valutazione.esito)

    def test_senza_node_vale_la_pagina(self):
        from unittest import mock

        with mock.patch("rischi.calcolo.shutil.which", return_value=None):
            risposta = self.salva(self.dettaglio, {"pl": "e", "pfh": 30, "ok": True})
        self.assertIn("calcolo della pagina", risposta.json()["messaggio"])
        self.assertEqual(self.funzione.valutazione.pl, "e")

    def test_plr_cambiato_rifa_il_confronto(self):
        self.salva(self.dettaglio)
        # 3 × 1500·10⁻⁹/h = 4,5·10⁻⁶/h → PL b: con S2 F1 P2 (PLr d) il requisito non è soddisfatto
        from .models import ArticoloSicurezza

        ArticoloSicurezza.objects.update(pfh=1500)
        self.salva(self.dettaglio)
        self.funzione.refresh_from_db()
        self.assertEqual((self.funzione.valutazione.pl, self.funzione.valutazione.esito), ("b", False))
        self.client.post(reverse("funzione", args=[self.funzione.pk]), {"nome": "Porta", "s": "S1", "f": "F1", "p": "P1"})
        self.funzione.refresh_from_db()
        self.assertEqual((self.funzione.plr, self.funzione.valutazione.esito), ("a", True))
        # PFH oltre il campo della PL a: nessun PL, il campo resta vuoto
        ArticoloSicurezza.objects.update(pfh=1e6)
        self.salva(self.dettaglio)
        self.funzione.refresh_from_db()
        self.assertEqual((self.funzione.valutazione.pl, self.funzione.valutazione.esito), ("", False))

    def test_sola_lettura(self):
        self.assertEqual(self.salva(self.dettaglio, utente=self.verificatore).status_code, 403)
        self.assertEqual(self.salva({"sottosistemi": "rotto"}).status_code, 400)
        self.client.force_login(self.verificatore)
        self.assertContains(self.client.get(self.url), "Sola lettura")


class ValidazioneTest(BaseConLibreria):
    """Fase 4: prove di validazione (EN ISO 13849-2), misure contro i guasti sistematici, flusso proprio e relazione."""

    def setUp(self):
        from .models import ArticoloSicurezza, FunzioneSicurezza

        self.analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.rev = self.analisi.revisione_corrente
        self.funzione = FunzioneSicurezza.objects.create(revisione=self.rev, nome="Porta di carico", s="S2", f="F1", p="P2")
        for chiave, tipo in (("fdi", "sensore"), ("fcpu", "logica"), ("sto", "attuatore")):
            ArticoloSicurezza.objects.create(
                chiave=chiave, codice=chiave.upper(), descrizione=f"Articolo {chiave}", tipo=tipo, pfh=10,
                fonte="Certificato", verificato=chiave != "sto",
            )
        blocco = lambda ruolo, chiave: {
            "id": chiave, "nome": chiave.upper(), "ruolo": ruolo, "percorso": "", "metodo": "pfh", "categoria": None,
            "componenti": [{"articoloId": chiave, "qty": 1}], "ccf": {}, "pfhK1": None,
        }
        self.dettaglio = {"sottosistemi": [blocco("rilevamento", "fdi"), blocco("logica", "fcpu"), blocco("attuazione", "sto")]}
        servizi.salva_valutazione(self.funzione, self.dettaglio, {}, self.compilatore)
        self.url_prove = reverse("prove_funzione", args=[self.funzione.pk])
        self.url_validazione = reverse("validazione", args=[self.rev.pk])
        # Prove standard ricavate dallo schema: funzionale, tempo, reset e i parametri dei tre blocchi "PFH da certificato"
        self.chiavi = ["funz:", "tempo", "reset", "param:fdi", "param:fcpu", "param:sto"]

    def post(self, url, corpo, utente=None):
        import json

        self.client.force_login(utente or self.compilatore)
        return self.client.post(url, json.dumps(corpo), content_type="application/json")

    def tutte_ok(self, **altro):
        return {"esiti": {k: {"esito": "ok"} for k in self.chiavi}, "esecutore": "M. Rossi", "data": "2026-10-17", **altro}

    def approva_analisi(self, rev=None):
        rev = rev or self.rev
        servizi.invia_in_verifica(rev, self.compilatore)
        servizi.segna_verificata(rev, self.verificatore)
        servizi.approva(rev, self.approvatore)
        rev.refresh_from_db()

    def test_prove_dallo_schema_e_funzione_validata(self):
        parziale = {"esiti": {"funz:": {"esito": "ok"}, "tempo": {"esito": "ko", "note": "1,2 s"}}}
        risposta = self.post(self.url_prove, {"dati": parziale, "prove": [{"key": "inventata"}]})
        self.assertEqual(risposta.status_code, 200, risposta.content)
        prove = self.funzione.__class__.objects.get(pk=self.funzione.pk).prove
        # Il server ricava le prove dallo schema, non dall'elenco inviato dalla pagina
        self.assertEqual((prove.validata, prove.da_eseguire, prove.non_ok), (False, 4, 1))
        self.assertEqual(prove.dati["esiti"]["tempo"], {"esito": "ko", "note": "1,2 s"})
        risposta = self.post(self.url_prove, {"dati": self.tutte_ok(extra=[{"id": "x1", "testo": "Prova a mano", "atteso": "Stop"}])})
        self.assertIn("1 da eseguire", risposta.json()["messaggio"])
        prove.refresh_from_db()
        self.assertEqual((prove.validata, prove.da_eseguire), (False, 1))  # la prova aggiunta non ha esito
        dati = self.tutte_ok(extra=[{"id": "x1", "testo": "Prova a mano", "atteso": "Stop"}])
        dati["esiti"]["extra:x1"] = {"esito": "na"}
        self.assertIn("funzione validata", self.post(self.url_prove, {"dati": dati}).json()["messaggio"])
        prove.refresh_from_db()
        self.assertTrue(prove.validata)

    def test_senza_node_vale_elenco_della_pagina(self):
        from unittest import mock

        with mock.patch("rischi.calcolo.shutil.which", return_value=None):
            risposta = self.post(self.url_prove, {"dati": {"esiti": {"funz:": {"esito": "ok"}}}, "prove": [{"key": "funz:"}]})
        self.assertIn("elenco della pagina", risposta.json()["messaggio"])
        self.assertTrue(self.funzione.__class__.objects.get(pk=self.funzione.pk).prove.validata)

    def test_dati_non_validi_e_ruoli(self):
        self.assertEqual(self.post(self.url_prove, {"dati": {"esiti": {"funz:": {"esito": "forse"}}}}).status_code, 400)
        self.assertEqual(self.post(self.url_prove, {"dati": {"data": "domani"}}).status_code, 400)
        self.assertEqual(self.post(self.url_prove, {"dati": self.tutte_ok()}, self.verificatore).status_code, 403)
        self.assertEqual(self.post(self.url_validazione, {"dati": {"esiti": {"deenergia": {"esito": "ok"}}}}, self.verificatore).status_code, 403)

    def test_sistematiche(self):
        risposta = self.post(self.url_validazione, {"dati": {"esiti": {"deenergia": {"esito": "ok"}, "vuota": {}}, "swFirma": "F-CRC 1A2B"}})
        self.assertEqual(risposta.status_code, 200, risposta.content)
        self.rev.validazione.refresh_from_db()
        self.assertEqual(self.rev.validazione.sistematiche, {"esiti": {"deenergia": {"esito": "ok"}}, "swVersione": "", "swFirma": "F-CRC 1A2B"})

    def test_flusso_dopo_l_approvazione_dell_analisi(self):
        from .models import RevisioneBloccata, ValidazioneSicurezza

        self.post(self.url_prove, {"dati": self.tutte_ok()})
        servizi.invia_validazione(self.rev, self.compilatore)
        servizi.verifica_validazione(self.rev, self.verificatore)
        with self.assertRaisesMessage(ValidationError, "Approva prima la revisione 0"):
            servizi.approva_validazione(self.rev, self.approvatore)
        servizi.rimanda_validazione(self.rev, self.verificatore, "Manca la prova di reset")
        self.approva_analisi()
        # Analisi approvata e bloccata: le prove si compilano lo stesso
        self.assertEqual(self.post(self.url_prove, {"dati": self.tutte_ok(esecutore="L. Bianchi")}).status_code, 200)
        servizi.invia_validazione(self.rev, self.compilatore)
        servizi.verifica_validazione(self.rev, self.verificatore)
        doppio = crea_utente("doppio", servizi.COMPILATORE, servizi.APPROVATORE)
        servizi.rimanda_validazione(self.rev, self.verificatore, "Ricontrolla")
        servizi.invia_validazione(self.rev, doppio)
        servizi.verifica_validazione(self.rev, self.verificatore)
        with self.assertRaises(PermissionDenied):
            servizi.approva_validazione(self.rev, doppio)
        servizi.approva_validazione(self.rev, self.approvatore)
        validazione = ValidazioneSicurezza.objects.get(revisione=self.rev)
        self.assertEqual(validazione.stato, ValidazioneSicurezza.Stato.APPROVATA)
        self.assertEqual(self.post(self.url_prove, {"dati": self.tutte_ok()}).status_code, 400)
        with self.assertRaises(RevisioneBloccata):
            validazione.prove.get().save()

    def test_nuova_revisione_riparte_dalla_validazione(self):
        self.post(self.url_prove, {"dati": self.tutte_ok()})
        self.post(self.url_validazione, {"dati": {"swVersione": "Linea 3 v2"}})
        self.approva_analisi()
        rev1 = servizi.nuova_revisione(self.analisi, self.compilatore, "Seconda porta")
        validazione = rev1.validazione
        self.assertEqual(validazione.stato, "BOZZA")
        self.assertEqual(validazione.sistematiche["swVersione"], "Linea 3 v2")
        prove = rev1.funzioni.get().prove
        self.assertTrue(prove.validata)
        self.assertEqual(prove.dati["esecutore"], "M. Rossi")
        # La validazione della revisione precedente non si tocca più
        self.assertFalse(self.rev.validazione.modificabile)
        self.assertEqual(self.post(self.url_prove, {"dati": self.tutte_ok()}).status_code, 400)

    def test_schema_cambiato_ricalcola_i_conteggi(self):
        self.post(self.url_prove, {"dati": self.tutte_ok()})
        dettaglio = {"sottosistemi": self.dettaglio["sottosistemi"] + [{
            "id": "rele", "nome": "Relè", "ruolo": "attuazione", "percorso": "", "metodo": "arch", "categoria": "3",
            "componenti": [], "ccf": {},
        }]}
        servizi.salva_valutazione(self.funzione, dettaglio, {}, self.compilatore)
        prove = self.funzione.__class__.objects.get(pk=self.funzione.pk).prove
        self.assertEqual((prove.validata, prove.da_eseguire), (False, 2))  # guasto e cortocircuito del relè

    def test_controlli(self):
        from .models import FunzioneSicurezza

        FunzioneSicurezza.objects.create(revisione=self.rev, nome="Arresto di emergenza", s="S2", f="F2", p="P1")
        messaggi = [a.messaggio for a in servizi.controlli(self.rev)]
        self.assertIn("Funzione di sicurezza «Arresto di emergenza»: PL non ancora calcolato.", messaggi)
        self.assertIn("1 articoli di sicurezza usati nei calcoli sono ancora da verificare: STO.", messaggi)
        quadro = servizi.quadro_validazione(self.rev)
        messaggi = [a.messaggio for a in quadro["anomalie"]]
        self.assertIn("La revisione 0 dell'analisi non è approvata: la validazione si approva dopo.", messaggi)
        self.assertIn("Funzione «Porta di carico»: prove di validazione non ancora compilate.", messaggi)
        self.assertTrue(any(m.startswith("Misure contro i guasti sistematici: 16 senza esito") for m in messaggi), messaggi)
        self.post(self.url_prove, {"dati": {"esiti": {"funz:": {"esito": "ko"}}}})
        messaggi = [a.messaggio for a in servizi.quadro_validazione(self.rev)["anomalie"]]
        self.assertIn("Funzione «Porta di carico»: 5 prove da eseguire.", messaggi)
        self.assertIn("Funzione «Porta di carico»: 1 prove non OK.", messaggi)
        self.assertIn("Funzione «Porta di carico»: indicare chi ha eseguito le prove e quando.", messaggi)

    def test_pagine(self):
        self.client.force_login(self.compilatore)
        pagina = self.client.get(self.url_validazione)
        self.assertContains(pagina, 'id="dati-validazione"')
        self.assertContains(pagina, "Compila le prove")
        self.assertContains(self.client.get(self.url_prove), "rischi/safety/validazione-pagina.js")
        self.assertContains(self.client.get(reverse("analisi", args=[self.analisi.pk])), "Validazione e relazione PDF")
        self.client.force_login(self.verificatore)
        self.assertContains(self.client.get(self.url_prove), "Sola lettura")

    def test_relazione_pdf(self):
        import io as _io

        from pypdf import PdfReader

        from .models import DocumentoGenerato

        self.post(self.url_prove, {"dati": self.tutte_ok()})
        self.client.force_login(self.compilatore)
        risposta = self.client.post(reverse("genera_documento", args=[self.rev.pk, "funzioni"]))
        self.assertEqual(risposta["Content-Type"], "application/pdf")
        documento = DocumentoGenerato.objects.get(tipo="FUNZIONI")
        self.assertFalse(documento.definitivo)
        testo = " ".join(p.extract_text() for p in PdfReader(_io.BytesIO(b"".join(risposta.streaming_content))).pages)
        for atteso in ("RELAZIONE SULLE FUNZIONI DI", "Porta di carico", "BOZZA", "requisito soddisfatto",
                       "Funzione validata", "M. Rossi", "17/10/2026", "Articolo sto", "Da verificare", "Schema a blocchi"):
            self.assertIn(atteso, testo)
        # Senza Node la relazione non si genera
        from unittest import mock

        with mock.patch("rischi.calcolo.shutil.which", return_value=None):
            risposta = self.client.post(reverse("genera_documento", args=[self.rev.pk, "funzioni"]))
        self.assertRedirects(risposta, self.url_validazione, fetch_redirect_response=False)
        # Validazione approvata: documento definitivo
        self.approva_analisi()
        servizi.invia_validazione(self.rev, self.compilatore)
        servizi.verifica_validazione(self.rev, self.verificatore)
        servizi.approva_validazione(self.rev, self.approvatore)
        self.client.post(reverse("genera_documento", args=[self.rev.pk, "funzioni"]))
        self.assertTrue(DocumentoGenerato.objects.filter(tipo="FUNZIONI").latest("generato_il").definitivo)
        # La dichiarazione UE cita la EN ISO 13849 quando la validazione è approvata
        from .documenti import norme_applicate

        codici = {n.codice for gruppo in norme_applicate(self.rev) for n in gruppo}
        self.assertTrue({"EN ISO 13849-1", "EN ISO 13849-2"} <= codici)


class VerificheElettricheTest(BaseConLibreria):
    """Fase 5: verifiche elettriche per quadro (IEC 60204-1, cap. 18), flusso proprio, documento e modulo."""

    def setUp(self):
        self.analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.rev = self.analisi.revisione_corrente
        self.client.force_login(self.compilatore)
        risposta = self.client.post(reverse("nuova_verifica_elettrica", args=[self.rev.pk]), {"quadro": "Quadro QE1"})
        self.verifica = self.rev.verifiche_elettriche.get()
        self.assertRedirects(risposta, reverse("verifica_elettrica", args=[self.verifica.pk]), fetch_redirect_response=False)
        self.url = reverse("verifica_elettrica", args=[self.verifica.pk])
        self.dati = {
            "tensione": "400 V 50 Hz TN-S", "strumento": "Fluke 1664 FC, matr. 123", "taratura": "2027-03-01",
            "vprova": "500 V c.c.", "esecutore": "L. Verdi", "data": "2026-10-17",
            "esiti": {k: {"esito": "ok"} for k in ("continuita", "anello", "isolamento", "tensione", "residue", "funzionali")},
            "extra": [],
            "equipotenziali": [{"id": "e1", "punto": "Telaio - morsetto PE", "conduttore": "G/V", "sezione": "16", "rpe": "0,02"}],
            "cavi": [
                {"id": "c1", "sigla": "W1", "l1pe": ">1", "l2pe": "250", "rpe": "0,05", "zs": "0,31", "in": "16"},
                {"id": "c2", "sigla": "W2", "l1pe": "0,4", "rpe": "0,07"},
            ],
        }

    def salva(self, dati=None, quadro="Quadro QE1", utente=None, risultato=None):
        import json

        self.client.force_login(utente or self.compilatore)
        corpo = {"quadro": quadro, "dati": dati if dati is not None else self.dati, "risultato": risultato or {}}
        return self.client.post(self.url, json.dumps(corpo), content_type="application/json")

    def test_salva_e_conteggi_dal_server(self):
        risposta = self.salva()
        self.assertEqual(risposta.status_code, 200, risposta.content)
        self.assertIn("isolamento non OK su 1 cavi", risposta.json()["messaggio"])
        self.verifica.refresh_from_db()
        self.assertEqual((self.verifica.da_eseguire, self.verifica.non_ok, self.verifica.isolamento_non_ok), (0, 0, 1))
        self.assertEqual(self.verifica.dati["cavi"][0]["l1pe"], ">1")
        dati = dict(self.dati, esiti={"continuita": {"esito": "ko", "misurato": "0,9", "note": "PE allentato"}},
                    extra=[{"id": "x", "testo": "Quadro QE2", "criterio": "≤ 0,1 Ω", "unita": "Ω"}])
        self.salva(dati, quadro="Quadro QE1 bordo macchina")
        self.verifica.refresh_from_db()
        self.assertEqual((self.verifica.quadro, self.verifica.da_eseguire, self.verifica.non_ok), ("Quadro QE1 bordo macchina", 6, 1))
        self.assertEqual(self.verifica.dati["esiti"]["continuita"]["misurato"], "0,9")

    def test_senza_node_valgono_i_conteggi_della_pagina(self):
        from unittest import mock

        risultato = {"riepilogo": {"aperte": 2, "ko": 0}, "registro": {"isoKo": []}}
        with mock.patch("rischi.calcolo.shutil.which", return_value=None):
            risposta = self.salva(risultato=risultato)
        self.assertIn("conteggi della pagina", risposta.json()["messaggio"])
        self.verifica.refresh_from_db()
        self.assertEqual((self.verifica.da_eseguire, self.verifica.isolamento_non_ok), (2, 0))

    def test_dati_non_validi_e_ruoli(self):
        self.assertEqual(self.salva(dict(self.dati, data="ieri")).status_code, 400)
        self.assertEqual(self.salva(dict(self.dati, cavi="W1")).status_code, 400)
        self.assertEqual(self.salva(dict(self.dati, esiti={"anello": {"esito": "boh"}})).status_code, 400)
        self.assertEqual(self.salva(quadro=" ").status_code, 400)
        self.assertEqual(self.salva(utente=self.verificatore).status_code, 403)

    def test_flusso_indipendente_dall_analisi(self):
        from .models import RevisioneBloccata

        self.salva()
        servizi.invia_verifica_elettrica(self.verifica, self.compilatore)
        self.assertEqual(self.salva().status_code, 400)  # in verifica: non si modifica
        servizi.segna_verifica_elettrica_verificata(self.verifica, self.verificatore)
        doppio = crea_utente("doppio", servizi.COMPILATORE, servizi.APPROVATORE)
        servizi.rimanda_verifica_elettrica(self.verifica, self.verificatore, "Manca la taratura")
        servizi.invia_verifica_elettrica(self.verifica, doppio)
        servizi.segna_verifica_elettrica_verificata(self.verifica, self.verificatore)
        with self.assertRaises(PermissionDenied):
            servizi.approva_verifica_elettrica(self.verifica, doppio)
        # L'analisi è ancora in bozza: la verifica elettrica si approva lo stesso
        servizi.approva_verifica_elettrica(self.verifica, self.approvatore)
        self.verifica.refresh_from_db()
        self.assertEqual(self.verifica.stato, "APPROVATA")
        with self.assertRaises(RevisioneBloccata):
            servizi.elimina_verifica_elettrica(self.verifica, self.compilatore)

    def test_nuova_revisione_copia_le_verifiche(self):
        self.salva()
        servizi.invia_in_verifica(self.rev, self.compilatore)
        servizi.segna_verificata(self.rev, self.verificatore)
        servizi.approva(self.rev, self.approvatore)
        rev1 = servizi.nuova_revisione(self.analisi, self.compilatore, "Nuovo quadro")
        copia = rev1.verifiche_elettriche.get()
        self.assertEqual((copia.quadro, copia.stato, copia.isolamento_non_ok), ("Quadro QE1", "BOZZA", 1))
        self.assertEqual(copia.dati["cavi"], self.verifica.__class__.objects.get(pk=self.verifica.pk).dati["cavi"])
        self.assertEqual(self.salva().status_code, 400)  # la verifica della revisione precedente non si tocca più
        with self.assertRaises(ValidationError):
            servizi.nuova_verifica_elettrica(self.rev, "QE2", self.compilatore)

    def test_controlli(self):
        self.salva(dict(self.dati, taratura="2026-01-31"))
        self.assertIn(
            "Verifica elettrica «Quadro QE1»: isolamento non OK su 1 cavi.", [a.messaggio for a in servizi.controlli(self.rev)]
        )
        from . import calcolo

        self.verifica.refresh_from_db()
        messaggi = [a.messaggio for a in servizi.controlli_verifica_elettrica(self.verifica, calcolo.elettriche(self.verifica.dati))]
        self.assertIn("Isolamento sotto 1 MΩ: W2.", messaggi)
        self.assertIn("Taratura dello strumento scaduta alla data delle prove.", messaggi)

    def test_documento_e_modulo(self):
        import io as _io

        from pypdf import PdfReader

        from .models import DocumentoGenerato

        self.salva()
        risposta = self.client.post(reverse("genera_verifica_elettrica", args=[self.verifica.pk]))
        testo = " ".join(p.extract_text() for p in PdfReader(_io.BytesIO(b"".join(risposta.streaming_content))).pages)
        for atteso in ("Verifiche dell'equipaggiamento elettrico", "Quadro QE1", "BOZZA", "Fluke 1664 FC", "01/03/2027",
                       "Telaio - morsetto PE", "Non OK", "max 0,07", "L. Verdi", "L1-PE"):
            self.assertIn(atteso, testo)
        documento = DocumentoGenerato.objects.get(tipo="ELETTRICHE")
        self.assertEqual((documento.verifica_elettrica, documento.definitivo), (self.verifica, False))
        modulo = self.client.get(reverse("modulo_verifica_elettrica", args=[self.verifica.pk]))
        self.assertEqual(modulo["Content-Type"], "application/pdf")
        testo = " ".join(p.extract_text() for p in PdfReader(_io.BytesIO(modulo.content)).pages)
        self.assertIn("Modulo rilievi", testo)
        self.assertIn("W2", testo)
        self.assertNotIn("0,07", testo)  # i valori misurati si scrivono a mano
        self.assertEqual(DocumentoGenerato.objects.count(), 1)  # il modulo non si archivia

    def test_pagine_ed_eliminazione(self):
        self.assertContains(self.client.get(reverse("analisi", args=[self.analisi.pk])), "Quadro QE1")
        pagina = self.client.get(self.url)
        self.assertContains(pagina, 'id="dati-verifica"')
        self.assertContains(pagina, "rischi/safety/verifiche-pagina.js")
        self.client.force_login(self.verificatore)
        self.assertContains(self.client.get(self.url), "Sola lettura")
        self.client.force_login(self.compilatore)
        self.client.post(reverse("azione_verifica_elettrica", args=[self.verifica.pk, "elimina"]))
        self.assertFalse(self.rev.verifiche_elettriche.exists())


class ChiusuraIntegrazioneTest(BaseConLibreria):
    """Fase 6: import delle valutazioni della safety evaluation, funzioni tipo, import delle librerie dei
    costruttori, EN 60204-1 nella dichiarazione."""

    def setUp(self):
        self.macchina = self.nuova_macchina()
        self.analisi = servizi.crea_analisi_da_libreria(self.macchina, self.compilatore)
        self.rev = self.analisi.revisione_corrente
        blocco = lambda ruolo, chiave: {
            "id": f"ss-{chiave}", "nome": chiave.upper(), "ruolo": ruolo, "percorso": "", "metodo": "pfh",
            "categoria": None, "componenti": [{"id": f"c-{chiave}", "articoloId": chiave, "qty": 1}], "ccf": {},
            "pfhK1": None,
        }
        # Come il file di "Esporta valutazione" della safety evaluation
        self.esportata = {
            "step": 7, "fSel": 0,
            "progetto": {"nome": "Isola robot", "macchina": "Isola robot R1", "cliente": "Kohler", "documento": "SE-25-20",
                         "revisione": 1, "data": "2026-09-30", "autore": "M. Rossi", "missionTime": 20},
            "funzioni": [
                {"id": "f1", "nome": "Arresto di emergenza", "descrizione": "Fungo: STO sugli assi", "S": "S2", "F": "F1",
                 "P": "P2", "sottosistemi": [blocco("rilevamento", "fdi"), blocco("logica", "fcpu"), blocco("attuazione", "sto")],
                 "validazione": {"esiti": {"funz:unico": {"esito": "ok", "note": "fungo pulpito"}},
                                 "extra": [{"id": "x1", "testo": "Fungo da quadro", "atteso": "Arresto"}],
                                 "esecutore": "M. Rossi", "data": "2026-09-30"}},
                {"id": "f2", "nome": "Porta di carico", "descrizione": "", "S": "S9", "F": "F2", "P": "P1", "sottosistemi": []},
            ],
            "sistematiche": {"esiti": {"g1": {"esito": "ok"}}, "swVersione": "V1.2", "swFirma": "F-CRC 3A9C"},
            "elettriche": {"quadro": "QE1", "tensione": "400 V", "esiti": {"continuita": {"esito": "ok"}}, "extra": [],
                           "cavi": [{"id": "c1", "sigla": "W1", "l1pe": "0,5", "rpe": "0,05"}]},
            "articoli": [
                {"id": k, "codice": k.upper(), "tipo": t, "pfh": 10, "fonte": "Certificato", "verificato": False}
                for k, t in (("fdi", "sensore"), ("fcpu", "logica"), ("sto", "attuatore"))
            ],
        }

    def importa(self, dati, utente=None):
        import json

        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(utente or self.compilatore)
        contenuto = dati if isinstance(dati, bytes) else json.dumps(dati).encode()
        return self.client.post(reverse("importa_safety_evaluation", args=[self.rev.pk]),
                                {"file": SimpleUploadedFile("valutazione.json", contenuto, "application/json")}, follow=True)

    def test_importa_valutazione_della_safety_evaluation(self):
        from .models import ArticoloSicurezza

        risposta = self.importa(self.esportata)
        testo = risposta.content.decode()
        self.assertIn("Importato SE-25-20 rev. 1: 2 funzioni di sicurezza; articoli di sicurezza 3 nuovi", testo)
        self.assertIn("prove di validazione di 1 funzioni", testo)
        self.assertIn("verifica elettrica «QE1»", testo)
        emergenza, porta = self.rev.funzioni.order_by("ordine")
        self.assertEqual((emergenza.nome, emergenza.descrizione, emergenza.plr), ("Arresto di emergenza", "Fungo: STO sugli assi", "d"))
        self.assertEqual((emergenza.valutazione.pl, emergenza.valutazione.pfh, emergenza.valutazione.esito), ("e", 30, True))
        self.assertNotIn("validazione", emergenza.valutazione.dettaglio)
        self.assertEqual(emergenza.valutazione.dettaglio["missionTime"], 20)
        self.assertEqual(emergenza.prove.dati["esecutore"], "M. Rossi")
        self.assertEqual(emergenza.prove.dati["extra"][0]["testo"], "Fungo da quadro")
        # S non valido: resta vuoto; senza sottosistemi niente calcolo
        self.assertEqual((porta.s, porta.f, porta.p), ("", "F2", "P1"))
        self.assertFalse(hasattr(porta, "valutazione"))
        self.assertEqual(self.rev.validazione.sistematiche["swFirma"], "F-CRC 3A9C")
        verifica = self.rev.verifiche_elettriche.get()
        self.assertEqual((verifica.quadro, verifica.isolamento_non_ok), ("QE1", 1))
        self.assertFalse(ArticoloSicurezza.objects.get(chiave="sto").verificato)
        # Un secondo import non sovrascrive: nomi distinti, misure sistematiche già compilate restano
        testo = self.importa(self.esportata).content.decode()
        self.assertIn("misure contro i guasti sistematici non importate perché già compilate", testo)
        self.assertTrue(self.rev.funzioni.filter(nome="Arresto di emergenza (2)").exists())

    def test_import_non_valido_o_non_permesso(self):
        self.assertIn("non è un file JSON leggibile", self.importa(b"\x00non json").content.decode())
        self.assertIn("manca l&#x27;elenco delle funzioni", self.importa({"articoli": []}).content.decode())
        # Componente senza articolo nel file né in libreria: si segnala
        dati = dict(self.esportata, articoli=[], elettriche={}, sistematiche={})
        self.assertIn("3 componenti senza articolo nella libreria", self.importa(dati).content.decode())
        # Solo il compilatore, solo in bozza
        self.importa(self.esportata, utente=self.verificatore)
        self.assertEqual(self.rev.funzioni.count(), 2)
        self.rev.stato = Revisione.Stato.APPROVATA
        self.rev.save()
        self.assertContains(self.importa(self.esportata), "è approvata: non è modificabile")
        self.assertEqual(self.rev.funzioni.count(), 2)

    def test_funzioni_tipo(self):
        from .models import FunzioneTipo

        self.importa(self.esportata)
        emergenza = self.rev.funzioni.get(nome="Arresto di emergenza")
        modulo = self.macchina.moduli.first()
        url = reverse("salva_come_funzione_tipo", args=[emergenza.pk])
        # Serve il permesso sulla libreria
        self.client.post(url, {"nome": "Arresto di emergenza Cosmap", "modulo": modulo.pk})
        self.assertFalse(FunzioneTipo.objects.filter(nome="Arresto di emergenza Cosmap").exists())
        capo = User.objects.create_superuser("capo", password="prova-prova-123")
        self.client.force_login(capo)
        self.assertContains(self.client.get(reverse("funzione", args=[emergenza.pk])), "Salva come funzione tipo")
        self.client.post(url, {"nome": "Arresto di emergenza Cosmap", "modulo": modulo.pk})
        tipo = FunzioneTipo.objects.get(nome="Arresto di emergenza Cosmap")
        self.assertEqual((tipo.modulo, tipo.s, tipo.plr, len(tipo.dettaglio["sottosistemi"])), (modulo, "S2", "d", 3))
        self.assertNotIn("validazione", tipo.dettaglio)
        # Stesso nome: rifiutata
        risposta = self.client.post(url, {"nome": "Arresto di emergenza Cosmap"}, follow=True)
        self.assertContains(risposta, "Esiste già una funzione tipo")
        # Libreria: elenco con lo schema a blocchi
        self.assertContains(self.client.get(reverse("admin:rischi_funzionetipo_change", args=[tipo.pk])), "FDI")
        # In un'altra macchina con lo stesso modulo si propone e si aggiunge
        altra = servizi.crea_analisi_da_libreria(self.nuova_macchina("25-21"), self.compilatore).revisione_corrente
        self.client.force_login(self.compilatore)
        pagina = self.client.get(reverse("analisi", args=[altra.analisi_id]))
        self.assertContains(pagina, "Funzioni tipo dei moduli della macchina non ancora aggiunte")
        risposta = self.client.post(reverse("aggiungi_funzione_tipo", args=[altra.pk]), {"funzione_tipo": tipo.pk})
        nuova = altra.funzioni.get()
        self.assertRedirects(risposta, reverse("funzione", args=[nuova.pk]), fetch_redirect_response=False)
        self.assertEqual((nuova.nome, nuova.plr, nuova.valutazione.pl), ("Arresto di emergenza Cosmap", "d", "e"))
        self.assertNotContains(self.client.get(reverse("analisi", args=[altra.analisi_id])), "non ancora aggiunte")
        # Una funzione tipo disattivata non si aggiunge
        tipo.attiva = False
        tipo.save()
        risposta = self.client.post(reverse("aggiungi_funzione_tipo", args=[altra.pk]), {"funzione_tipo": tipo.pk})
        self.assertEqual(risposta.status_code, 404)

    def test_importa_libreria_del_costruttore(self):
        import json

        from django.core.files.uploadedfile import SimpleUploadedFile

        from .models import ArticoloSicurezza

        capo = User.objects.create_superuser("capo", password="prova-prova-123")
        self.client.force_login(capo)
        self.assertContains(self.client.get(reverse("admin:rischi_articolosicurezza_changelist")), "Importa libreria del costruttore")
        url = reverse("admin:rischi_articolosicurezza_importa")
        pagina = self.client.get(url)
        self.assertContains(pagina, "rischi/safety/sistema.js")
        self.assertContains(pagina, "rischi/safety/vdma.js")
        articoli = [{"id": "piz-1", "codice": "FS 2996", "produttore": "Pizzato", "tipo": "sensore", "b10d": 2000000,
                     "fonte": "SISTEMA Pizzato", "libreria": "Pizzato A26", "immagine": "x.png"}]
        file = SimpleUploadedFile("articoli.json", json.dumps(articoli).encode(), "application/json")
        risposta = self.client.post(url, {"articoli": file})
        self.assertEqual(risposta.json()["messaggio"], "Articoli di sicurezza: 1 nuovi, 0 aggiornati, 0 invariati.")
        self.assertFalse(ArticoloSicurezza.objects.get(chiave="piz-1").verificato)
        file = SimpleUploadedFile("articoli.json", b'[{"codice": "senza id"}]', "application/json")
        self.assertEqual(self.client.post(url, {"articoli": file}).status_code, 400)
        # Senza permesso sulla libreria
        self.client.force_login(self.compilatore)
        self.assertNotEqual(self.client.get(url).status_code, 200)

    def test_dichiarazione_cita_en_60204_1(self):
        from .documenti import norme_applicate
        from .models import Norma, VerificaElettrica

        Norma.objects.get_or_create(codice="EN 60204-1", defaults={"armonizzata": True})
        codici = lambda: {n.codice for gruppo in norme_applicate(self.rev) for n in gruppo}
        presente_prima = "EN 60204-1" in codici()  # può già venire dalle schede della libreria
        prima = VerificaElettrica.objects.create(revisione=self.rev, quadro="QE1", stato=VerificaElettrica.Stato.APPROVATA)
        seconda = VerificaElettrica.objects.create(revisione=self.rev, quadro="QE2")
        self.assertEqual("EN 60204-1" in codici(), presente_prima)
        seconda.stato = VerificaElettrica.Stato.APPROVATA
        seconda.save()
        self.assertIn("EN 60204-1", codici())
        self.assertTrue(prima.pk)


class MotoreJavaScriptTest(TestCase):
    """I test Node della safety evaluation (motore, schema, validazione, lettori delle librerie) girano con quelli
    Django: rischi/js_test, sui file di rischi/static/rischi/safety."""

    def test_node(self):
        import shutil
        import subprocess
        import unittest

        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node non installato")
        cartella = Path(settings.BASE_DIR) / "rischi" / "js_test"
        file = sorted(str(f) for f in cartella.glob("*.test.js"))
        esito = subprocess.run([node, "--test", *file], capture_output=True, text=True, timeout=120)
        self.assertEqual(esito.returncode, 0, esito.stdout[-3000:] + esito.stderr[-2000:])


class LibreriaSicurezzaTest(TestCase):
    """Libreria divisa tra analisi e sicurezza funzionale; funzioni proposte dalle misure; funzioni tipo Cosmap."""

    @classmethod
    def setUpTestData(cls):
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        cls.compilatore = crea_utente("mario", servizi.COMPILATORE)
        commessa = Commessa.objects.create(
            numero="26-80", cliente=Cliente.objects.create(ragione_sociale="Prova"), anno=2026,
            riferimento=RiferimentoNormativo.objects.get(),
        )
        cls.macchina = Macchina.objects.create(commessa=commessa, denominazione="Cella")
        cls.macchina.moduli.set(servizi.moduli_proposti() | Modulo.objects.filter(sigla__in=["CAB", "TAV"]))
        cls.analisi = servizi.crea_analisi_da_libreria(cls.macchina, cls.compilatore)

    def test_gruppi_della_libreria(self):
        capo = User.objects.create_superuser("capo", password="prova-prova-123")
        self.client.force_login(capo)
        pagina = self.client.get(reverse("admin:index")).content.decode()
        analisi = pagina.index("Libreria – analisi dei rischi")
        sicurezza = pagina.index("Libreria – sicurezza funzionale")
        commesse = pagina.index("Commesse e dati aziendali")
        self.assertLess(analisi, sicurezza)
        self.assertLess(sicurezza, commesse)
        self.assertLess(sicurezza, pagina.index("Funzioni tipo"))
        self.assertLess(pagina.index("Funzioni tipo"), commesse)
        self.assertLess(pagina.index("Schede modello"), sicurezza)

    def test_misure_proposte_come_funzioni(self):
        from .models import FunzioneSicurezza

        rev = self.analisi.revisione_corrente
        proposte = servizi.misure_per_funzioni(rev)
        porte = next(p for p in proposte if p[0].scheda.codice == "CAB-04" and "interblocco" in p[0].testo)
        misura, s, f, p, plr = porte
        self.assertEqual((s, f, p), servizi.sfp_suggeriti(misura.scheda))
        self.assertEqual(s, "S2")  # Se iniziale 4

        self.client.force_login(self.compilatore)
        self.assertContains(self.client.get(reverse("analisi", args=[self.analisi.pk])), "possono diventare funzioni di sicurezza")
        pagina = self.client.get(reverse("nuova_funzione", args=[rev.pk]) + f"?misura={misura.pk}")
        self.assertContains(pagina, "suggeriti dalla stima iniziale")
        self.assertEqual(pagina.context["form"].initial["s"], "S2")

        funzione = FunzioneSicurezza.objects.create(revisione=rev, nome="Porte", s=s, f=f, p=p)
        funzione.misure.add(misura)
        self.assertNotIn(misura, [p[0] for p in servizi.misure_per_funzioni(rev)])

    def test_funzioni_tipo_cosmap_dei_moduli(self):
        from .models import FunzioneTipo

        cabina = FunzioneTipo.objects.get(nome="Arresto all'apertura delle porte interbloccate")
        self.assertEqual((cabina.modulo.sigla, cabina.plr), ("CAB", "d"))
        self.assertTrue(FunzioneTipo.objects.filter(nome="Arresto di emergenza", modulo__isnull=True).exists())
        proposte = {t.nome for t in servizi.funzioni_tipo_per(self.macchina)}
        self.assertIn("Consenso alla rotazione della tavola", proposte)
        self.assertNotIn("Barriera della zona di carico pallet", proposte)
        # Rilanciare l'import non duplica
        call_command("importa_libreria", str(LIBRERIA.parent / "Libreria_nuova_Cosmap.xlsx"), stdout=io.StringIO())
        self.assertEqual(FunzioneTipo.objects.filter(nome=cabina.nome).count(), 1)


class PaginaFunzioneTest(TestCase):
    """Pagina della funzione: sezioni apribili e grafico del PL."""

    def test_grafico_pl(self):
        from . import grafico_pl

        svg = grafico_pl.svg("d", 52.7, "d", [{"nome": "Barriere", "pfh": 31.9, "pl": "d"}, {"nome": "Ripari", "pfh": 28, "pl": "d"}],
                             [{"nome": "Logica", "pfh": 1, "pl": "e"}])
        self.assertIn("PL d (PLr)", svg)
        self.assertIn("Percorso Barriere", svg)
        self.assertIn("5,27·10⁻⁸/h", svg)
        self.assertEqual(svg.count("<circle"), 4)

    def test_sezioni_e_grafico_nella_pagina(self):
        from .models import FunzioneSicurezza, ValutazioneFunzione

        call_command("importa_libreria", str(LIBRERIA), stdout=io.StringIO())
        compilatore = crea_utente("mario", servizi.COMPILATORE)
        commessa = Commessa.objects.create(
            numero="26-90", cliente=Cliente.objects.create(ragione_sociale="Prova"), anno=2026,
            riferimento=RiferimentoNormativo.objects.get(),
        )
        macchina = Macchina.objects.create(commessa=commessa, denominazione="Cella")
        macchina.moduli.set(servizi.moduli_proposti())
        rev = servizi.crea_analisi_da_libreria(macchina, compilatore).revisione_corrente
        funzione = FunzioneSicurezza.objects.create(revisione=rev, nome="Porte", s="S2", f="F1", p="P2")
        self.client.force_login(compilatore)
        pagina = self.client.get(reverse("funzione", args=[funzione.pk]))
        self.assertContains(pagina, 'class="sezione"', count=5)
        self.assertContains(pagina, "Apri tutte le sezioni")
        self.assertNotContains(pagina, "grafico-pl")
        self.assertContains(pagina, "grafo-plr")  # grafo del rischio nella sezione 3
        html = pagina.content.decode()
        self.assertLess(html.index("5. VALIDAZIONE"), html.index("Salva funzione"))
        self.assertLess(html.index("Salva funzione"), html.index("Elimina funzione"))
        ValutazioneFunzione.objects.create(funzione=funzione, dettaglio={}, pl="d", pfh=120.0, esito=True)
        self.assertContains(self.client.get(reverse("funzione", args=[funzione.pk])), "grafico-pl")


class SezioniApribiliTest(TestCase):
    def test_script_delle_sezioni_in_tutte_le_pagine(self):
        utente = crea_utente("mario", servizi.COMPILATORE)
        self.client.force_login(utente)
        self.assertContains(self.client.get(reverse("elenco_commesse")), "rischi/sezioni.js")

    def test_sezioni_anche_nella_libreria(self):
        admin = User.objects.create_superuser("capo", "c@example.com", "x")
        self.client.force_login(admin)
        for url in (reverse("admin:index"), reverse("admin:rischi_norma_add")):
            pagina = self.client.get(url)
            self.assertContains(pagina, "rischi/sezioni.js")
            self.assertContains(pagina, "rischi/sezioni.css")


class GrafoPLrTest(TestCase):
    def test_percorso_evidenziato(self):
        from .grafico_pl import svg_grafo

        grafo = svg_grafo("S2", "F1", "P2")
        self.assertIn('class="ramo attivo" data-chiave="S2"', grafo)
        self.assertIn('class="ramo attivo" data-chiave="S2F1"', grafo)
        self.assertIn('class="foglia attivo" data-chiave="S2F1P2"', grafo)
        self.assertIn('class="ramo" data-chiave="S1"', grafo)
        self.assertEqual(grafo.count(" attivo"), 4)  # 3 rami e la foglia d
        self.assertNotIn(" attivo", svg_grafo())
