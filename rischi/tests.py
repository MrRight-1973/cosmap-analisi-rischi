from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import Group, User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from . import servizi
from .models import (
    Caratteristica,
    Cliente,
    Commessa,
    Esito,
    Macchina,
    MetodoStima,
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
        call_command("importa_libreria", str(LIBRERIA), stdout=open("/dev/null", "w"))
        cls.compilatore = crea_utente("mario", servizi.COMPILATORE)
        cls.verificatore = crea_utente("lucia", servizi.VERIFICATORE)
        cls.approvatore = crea_utente("titolare", servizi.APPROVATORE)
        cls.riferimento = RiferimentoNormativo.objects.get()
        cls.cliente = Cliente.objects.create(ragione_sociale="Kohler")

    def nuova_macchina(self, numero="25-20", *caratteristiche):
        commessa = Commessa.objects.create(
            numero=numero, cliente=self.cliente, anno=2020, riferimento=self.riferimento
        )
        macchina = Macchina.objects.create(commessa=commessa, denominazione="Impianto di prova", matricola="X1")
        macchina.caratteristiche.set(Caratteristica.objects.filter(nome__in=caratteristiche))
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
        call_command("importa_libreria", str(LIBRERIA), stdout=open("/dev/null", "w"))
        self.assertEqual(SchedaModello.objects.count(), 78)


class CreazioneAnalisiTest(BaseConLibreria):
    def test_solo_moduli_attivati(self):
        sempre = SchedaModello.objects.filter(modulo__sempre_attivo=True).count()
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        self.assertEqual(analisi.revisione_corrente.schede.count(), sempre)

        tavola = "Tavola rotante con carico/scarico manuale"
        con_tavola = SchedaModello.objects.filter(modulo__caratteristiche__nome=tavola).count()
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
                "caratteristiche": [Caratteristica.objects.first().pk],
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
        self.assertEqual(self.client.get(reverse("registro")).status_code, 200)

    def test_modifica_scheda_da_form(self):
        self.client.force_login(self.compilatore)
        analisi = servizi.crea_analisi_da_libreria(self.nuova_macchina(), self.compilatore)
        scheda = analisi.revisione_corrente.schede.filter(misure__isnull=False).first()
        pagina = self.client.get(reverse("scheda", args=[scheda.pk]))
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

    @staticmethod
    def leggi(contenuto):
        import io

        import docx

        d = docx.Document(io.BytesIO(contenuto))
        parti = [p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells]
        parti += [p.text for s in d.sections for p in s.header.paragraphs]
        return "\n".join(parti)

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

    def test_genera_da_pagina_e_archivia(self):
        from .models import DocumentoGenerato

        self.client.force_login(self.compilatore)
        risposta = self.client.post(reverse("genera_documento", args=[self.rev.pk, "dichiarazione"]), {"lingua": "en"})
        self.assertEqual(risposta.status_code, 200)
        self.assertIn("_BOZZA_en.docx", risposta["Content-Disposition"])
        documento = DocumentoGenerato.objects.get()
        self.assertFalse(documento.definitivo)
        self.assertContains(self.client.get(reverse("analisi", args=[self.analisi.pk])), "Scarica")
        self.assertEqual(self.client.get(reverse("scarica_documento", args=[documento.pk])).status_code, 200)

        self.approva()
        self.client.post(reverse("genera_documento", args=[self.rev.pk, "valutazione"]))
        self.assertTrue(DocumentoGenerato.objects.get(tipo="VALUTAZIONE").definitivo)


class AmministrazioneCaratteristicheTest(BaseConLibreria):
    def test_moduli_si_scelgono_dalla_caratteristica(self):
        from .models import Modulo

        admin_utente = User.objects.create_superuser("capo", password="prova-prova-123")
        self.client.force_login(admin_utente)
        robot = Modulo.objects.get(nome__startswith="Gruppo di smerigliatura")
        zona = Modulo.objects.get(nome__startswith="Zona smerigliatura")
        risposta = self.client.post(
            reverse("admin:rischi_caratteristica_add"),
            {"nome": "Robot antropomorfo", "descrizione": "", "moduli": [robot.pk, zona.pk]},
        )
        self.assertEqual(risposta.status_code, 302)
        nuova = Caratteristica.objects.get(nome="Robot antropomorfo")
        self.assertEqual(set(nuova.moduli.all()), {robot, zona})

        pagina = self.client.get(reverse("admin:rischi_caratteristica_change", args=[nuova.pk]))
        self.assertContains(pagina, "Moduli da attivare")
        self.assertContains(self.client.get(reverse("admin:rischi_modulo_changelist")), "Robot antropomorfo")

        macchina = self.nuova_macchina("28-01", "Robot antropomorfo")
        analisi = servizi.crea_analisi_da_libreria(macchina, self.compilatore)
        self.assertTrue(analisi.revisione_corrente.schede.filter(modulo=robot).exists())
