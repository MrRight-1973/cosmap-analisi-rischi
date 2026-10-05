from django.db import migrations

FIGURE = [
    ("Operatore di conduzione", "OPERATORE",
     "Avvia e sorveglia il ciclo, carica e scarica i pezzi, controlla la lavorazione."),
    ("Operatore di attrezzaggio", "OPERATORE",
     "Cambia formato, attrezzature e utensili; esegue le regolazioni previste dal manuale."),
    ("Manutentore meccanico", "OPERATORE",
     "Personale qualificato per la manutenzione meccanica, pneumatica e oleodinamica."),
    ("Manutentore elettrico", "OPERATORE",
     "Personale qualificato (PES/PAV) per gli interventi sull'equipaggiamento elettrico."),
    ("Programmatore", "OPERATORE", "Programma robot, CNC e parametri di processo."),
    ("Addetto alle pulizie", "OPERATORE", "Pulisce la macchina e la zona circostante."),
    ("Installatore / collaudatore", "OPERATORE",
     "Personale del fabbricante o incaricato per trasporto, installazione, messa in servizio e smantellamento."),
    ("Terzi di passaggio", "ESPOSTA",
     "Persone che non lavorano alla macchina ma possono trovarsi nelle vicinanze "
     "(es. carrellisti, personale di altri reparti)."),
]


def crea(apps, schema_editor):
    Figura = apps.get_model("rischi", "Figura")
    for ordine, (nome, tipo, descrizione) in enumerate(FIGURE):
        Figura.objects.get_or_create(nome=nome, defaults={"tipo": tipo, "descrizione": descrizione, "ordine": ordine})


class Migration(migrations.Migration):
    dependencies = [("rischi", "0006_soggetti_esposti")]

    operations = [migrations.RunPython(crea, migrations.RunPython.noop)]
