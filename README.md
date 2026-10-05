# Cosmap – Analisi dei rischi

Prototipo dell'applicazione interna per compilare l'analisi dei rischi delle
macchine Cosmap secondo il Regolamento (UE) 2023/1230.

La struttura dati segue il documento "Struttura dati – Analisi rischi Cosmap":

- **Libreria**: moduli (con le loro schede), schede modello, misure, pericoli (EN ISO 12100 all. B),
  requisiti RESS, norme, metodo di stima (ISO/TR 14121-2 ibrido). Si gestisce
  dalla sezione "Libreria e utenti" (amministrazione).
- **Analisi di commessa**: commessa → macchina → analisi → revisioni → schede.
  Ogni revisione contiene una copia completa delle schede; una revisione
  approvata non si modifica più.
- **Ruoli**: Compilatore, Verificatore, Approvatore. Chi compila una revisione
  non può approvarla.
- **Registro modifiche**: ogni modifica è registrata con utente e valori prima/dopo.

## Cosa fa il prototipo

1. Importa la libreria da un file Excel: `dati/Libreria_nuova_Cosmap.xlsx` (scritta da zero
   sul Regolamento 2023/1230, misure classificate per tipo, stime da validare) oppure la
   libreria precedente `dati/Libreria_analisi_rischi_Cosmap.xlsx`. La libreria nuova si
   modifica nel sorgente `dati/genera_libreria_nuova.py` e si rigenera con
   `python dati/genera_libreria_nuova.py`; `dati/confronta_librerie.py` produce il confronto
   con la libreria precedente (`dati/Confronto_librerie.xlsx`).
2. Crea una commessa con la sua macchina: si scelgono i moduli della libreria e
   l'analisi propone le loro schede, oppure si copia un'analisi già approvata.
   I moduli si cambiano anche dopo, dai dati della macchina, finché la revisione
   è in bozza: le schede dei moduli aggiunti entrano come proposte, quelle dei
   moduli tolti escono solo se ancora da decidere.
3. Il compilatore conferma, modifica o scarta ogni scheda (lo scarto richiede
   la motivazione), compila stime e misure, segna i requisiti non applicabili.
4. Classe ed esito si calcolano dalla matrice del metodo, come nel file Excel.
5. Prima della verifica segnala: requisiti senza scheda, stime finali mancanti,
   esiti non verdi senza rischio residuo, proposte non decise.
6. Flusso Bozza → In verifica → Approvata, con rimando in bozza e nuova revisione.
7. Genera in Word la valutazione dei rischi, l'elenco dei rischi residui per il
   manuale e la dichiarazione UE di conformità (italiano o inglese). Ogni
   documento generato resta archiviato; da una revisione non approvata esce
   con la scritta BOZZA.

La dichiarazione elenca come "norme armonizzate" solo le norme segnate come
armonizzate nella libreria; le altre norme citate nelle schede compaiono come
"altre norme". I testi fissi della dichiarazione vanno confrontati con
l'Allegato V del Regolamento prima dell'uso.

Le misure importate dal file Excel sono un unico testo per scheda, con tipo
"Da classificare": vanno divise e classificate durante la revisione della libreria.

## Avvio su un PC (prova)

Serve Python 3.11 o successivo.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py importa_libreria dati/Libreria_analisi_rischi_Cosmap.xlsx
python manage.py crea_ruoli
python manage.py createsuperuser
python manage.py runserver
```

Aprire http://127.0.0.1:8000, entrare con l'utente creato e, da
"Libreria e utenti", creare gli utenti assegnando i gruppi
Compilatore / Verificatore / Approvatore.

Senza variabili d'ambiente il prototipo usa un database SQLite locale (`db.sqlite3`).
Per provare un'altra libreria senza toccare i propri dati si usa un database separato:

```powershell
$env:SQLITE_PATH = "db-libreria-nuova.sqlite3"
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py importa_libreria dati/Libreria_nuova_Cosmap.xlsx
```

## Server interno con PostgreSQL

1. Creare database e utente PostgreSQL.
2. Impostare le variabili d'ambiente del servizio come in `.env.example`
   (con `POSTGRES_DB` impostata si usa PostgreSQL).
3. Eseguire `migrate`, `importa_libreria`, `crea_ruoli`, `createsuperuser`
   e `collectstatic`.
4. Servire l'applicazione con un server WSGI (es. gunicorn o waitress) dietro
   il web server aziendale, raggiungibile solo dalla rete interna e dalla VPN.
5. Includere il database e la cartella `media/` nei backup aziendali.

## Test

```bash
python manage.py test rischi
```
