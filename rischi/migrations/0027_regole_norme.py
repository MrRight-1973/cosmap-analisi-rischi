"""Regole per le norme automatiche: norme tipiche dei requisiti RESS e parole chiave delle soluzioni.

Si collegano solo le norme già in libreria; tutto resta modificabile dall'amministrazione."""

from django.db import migrations

NORME_REQUISITI = {
    "1.1.2": ["EN ISO 12100"],
    "1.1.4": ["EN 1837"],
    "1.1.6": ["EN 614-1", "EN 1005-2", "EN ISO 14738"],
    "1.1.7": ["EN 614-1", "EN ISO 14738"],
    "1.1.9": ["EN ISO 13849-1", "EN IEC 62443-3-3"],
    "1.2.1": ["EN ISO 13849-1", "EN ISO 13849-2", "EN IEC 62061"],
    "1.2.2": ["EN 60204-1", "EN 61310-1"],
    "1.2.3": ["EN 60204-1", "EN ISO 14118"],
    "1.2.4.1": ["EN 60204-1"],
    "1.2.4.2": ["EN 60204-1", "EN ISO 13849-1"],
    "1.2.4.3": ["EN ISO 13850", "EN 60204-1"],
    "1.2.4.4": ["EN ISO 11161", "EN ISO 13850"],
    "1.2.5": ["EN 60204-1", "EN ISO 13849-1"],
    "1.2.6": ["EN 60204-1", "EN ISO 14118"],
    "1.3.3": ["EN ISO 14120"],
    "1.3.7": ["EN ISO 14120", "EN ISO 13857", "EN ISO 13854"],
    "1.3.8.1": ["EN ISO 14120", "EN ISO 13857"],
    "1.3.8.2": ["EN ISO 14120", "EN ISO 14119", "EN ISO 13857", "EN ISO 13855"],
    "1.3.9": ["EN ISO 4414", "EN ISO 14118"],
    "1.4.1": ["EN ISO 14120"],
    "1.4.2.1": ["EN ISO 14120", "EN ISO 13857"],
    "1.4.2.2": ["EN ISO 14119", "EN ISO 14120", "EN ISO 13849-1"],
    "1.4.2.3": ["EN ISO 14120"],
    "1.4.3": ["EN IEC 61496-1", "EN ISO 13855", "EN ISO 13849-1"],
    "1.5.1": ["EN 60204-1", "EN IEC 61439-1"],
    "1.5.3": ["EN ISO 4414"],
    "1.5.4": ["EN 60204-1"],
    "1.5.5": ["EN ISO 13732-1"],
    "1.5.6": ["EN ISO 19353"],
    "1.5.7": ["EN 1127-1"],
    "1.5.8": ["EN ISO 11688-1", "EN ISO 3744", "EN ISO 11202", "EN ISO 4871"],
    "1.5.13": ["EN ISO 14123-1"],
    "1.5.14": ["EN ISO 14119"],
    "1.5.15": ["EN ISO 14122-2"],
    "1.6.1": ["EN ISO 14118"],
    "1.6.2": ["EN ISO 14122-2", "EN ISO 14122-3"],
    "1.6.3": ["EN ISO 14118", "EN 60204-1"],
    "1.6.4": ["EN ISO 14118"],
    "1.7.1.1": ["EN 61310-1"],
    "1.7.1.2": ["EN 61310-1"],
    "1.7.2": ["EN ISO 7010", "EN 61310-1"],
    "1.7.4.1": ["EN ISO 20607"],
    "1.7.4.2": ["EN ISO 20607"],
}

PAROLE_CHIAVE = {
    "Arresto di emergenza": "emergenza, fungo",
    "Aspirazione di polveri e sostanze": "aspirazione localizzata, aspirazione delle polveri, aspirazione polveri, "
    "impianto di aspirazione, in depressione, captazione",
    "Barriera fotoelettrica": "barriera, barriere, fotoelettric, elettrosensibil, scanner",
    "Equipaggiamento elettrico conforme": "equipaggiamento elettrico, quadro elettrico, messa a terra",
    "Funzioni di sicurezza del sistema di comando": "funzioni di sicurezza, funzione di sicurezza, pl richiesto, "
    "plr, relè di sicurezza, plc di sicurezza",
    "Illuminazione integrata": "illuminazion",
    "Impianto pneumatico conforme": "pneumatic, aria compressa, senza aria",
    # Niente parole chiave per le istruzioni: quasi ogni scheda rimanda al manuale (la EN ISO 20607 sta nel 1.7.4).
    "Piattaforme e passerelle": "piattaform, passerell, parapett, scala fissa, scale fisse",
    "Postazione ergonomica": "ergonomic, altezza di carico, altezza di lavoro",
    "Prevenzione dell'avviamento inatteso": "sezionator, lucchett, consegna, avviamento inatteso, non riparte",
    "Protezione dalle superfici calde": "superfici calde, temperatura, ustion",
    "Riduzione del rumore alla fonte": "silenziator, fonoassorb, bassa rumorosità, sorgenti di rumore, "
    "rumore ridott",
    "Riparo fisso": "riparo fisso, ripari fissi, pannelli fissi, ripari perimetrali, con attrezzo, carter",
    "Riparo mobile interbloccato": "interblocc",
    "Riparo mobile interbloccato con bloccaggio": "bloccaggio, elettroserratur",
    "Segnaletica di sicurezza": "segnaletica, cartell, pittogramm, segnali di avvertimento, segnali di pericolo, "
    "segnali di obbligo, segnali di divieto, iso 7010",
    "Spazi minimi contro lo schiacciamento": "spazi minimi, schiacciament",
}


def carica(apps, schema_editor):
    Norma = apps.get_model("rischi", "Norma")
    Requisito = apps.get_model("rischi", "RequisitoRESS")
    Soluzione = apps.get_model("rischi", "SoluzioneProtezione")
    for codice, codici_norme in NORME_REQUISITI.items():
        norme = list(Norma.objects.filter(codice__in=codici_norme))
        for requisito in Requisito.objects.filter(codice=codice):
            if not requisito.norme.exists():
                requisito.norme.set(norme)
    for nome, parole in PAROLE_CHIAVE.items():
        Soluzione.objects.filter(nome=nome, parole_chiave="").update(parole_chiave=parole)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0026_norme_automatiche")]
    operations = [migrations.RunPython(carica, migrations.RunPython.noop)]
