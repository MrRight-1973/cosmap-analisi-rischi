"""Capitoli iniziali della valutazione: Definizioni e Principi generali (Allegato III, parti A e B del
Regolamento (UE) 2023/1230). Restano modificabili da Libreria e utenti → Capitoli della valutazione."""

from django.db import migrations

DEFINIZIONI = (
    "Le schede usano le definizioni dell'Allegato III, parte A, del Regolamento (UE) 2023/1230. "
    "Il riferimento alla lettera è indicato nel titolo di ogni sezione delle schede.<br><br>"
    "Ai fini del presente allegato si intende per:<br>"
    "a) «pericolo»: una potenziale fonte di lesione o danno alla salute;<br>"
    "b) «zona pericolosa»: qualsiasi zona all'interno e/o in prossimità di una macchina o di un prodotto correlato "
    "in cui la presenza di una persona costituisca un rischio per la sicurezza o la salute di detta persona;<br>"
    "c) «persona esposta»: qualsiasi persona che si trovi interamente o in parte in una zona pericolosa;<br>"
    "d) «operatore»: la persona o le persone incaricate di installare, di far funzionare, di regolare, di pulire, "
    "di riparare e di spostare una macchina o un prodotto correlato o di eseguirne la manutenzione;<br>"
    "e) «rischio», combinazione della probabilità e della gravità di una lesione o di un danno per la salute che "
    "possano insorgere in una situazione pericolosa;<br>"
    "f) «riparo»: elemento di una macchina o di un prodotto correlato utilizzato specificamente per garantire la "
    "protezione tramite una barriera materiale;<br>"
    "g) «dispositivo di protezione»: dispositivo (diverso da un riparo) che riduce il rischio, da solo o associato "
    "ad un riparo;<br>"
    "h) «uso previsto»: l'uso di una macchina o di un prodotto correlato conformemente alle informazioni fornite "
    "nelle istruzioni per l'uso;<br>"
    "i) «uso scorretto ragionevolmente prevedibile»: l'uso di una macchina o di un prodotto correlato in un modo "
    "diverso da quello indicato nelle istruzioni per l'uso, ma che può derivare dal comportamento umano facilmente "
    "prevedibile."
)

PRINCIPI = (
    "<i>Allegato III, parte B, del Regolamento (UE) 2023/1230.</i><br><br>"
    "1. Il fabbricante di una macchina o di un prodotto correlato deve provvedere affinché sia effettuata una "
    "valutazione del rischio per stabilire i requisiti essenziali di sicurezza e di tutela della salute che "
    "concernono la macchina o il prodotto correlato. La macchina o il prodotto correlato devono inoltre essere "
    "progettati e costruiti per eliminare i rischi o, ove non sia possibile, ridurre al minimo tutti i rischi "
    "pertinenti, tenendo conto dei risultati della valutazione del rischio.<br>"
    "Con il processo iterativo della valutazione del rischio e della riduzione del rischio di cui al primo comma, "
    "il fabbricante:<br>"
    "a) stabilisce i limiti della macchina o del prodotto correlato, il che comprende l'uso previsto e l'uso "
    "scorretto ragionevolmente prevedibile;<br>"
    "b) individua i pericoli cui può dare origine la macchina o il prodotto correlato e le situazioni pericolose "
    "che ne derivano;<br>"
    "c) stima i rischi, tenendo conto della gravità dell'eventuale lesione o danno alla salute e della probabilità "
    "che si verifichi;<br>"
    "d) valuta i rischi al fine di stabilire se sia richiesta una riduzione del rischio conformemente "
    "all'obiettivo del presente regolamento;<br>"
    "e) elimina i pericoli o riduce i rischi che ne derivano, applicando le misure di protezione nell'ordine "
    "indicato nel punto 1.1.2, lettera b).<br>"
    "La valutazione del rischio e la riduzione del rischio includono i pericoli che possono manifestarsi durante "
    "il ciclo di vita della macchina o del prodotto correlato prevedibili al momento dell'immissione della "
    "macchina o del prodotto correlato sul mercato come un'evoluzione prevista del suo comportamento o della sua "
    "logica integralmente o parzialmente autoevolutivi in ragione del fatto che tale macchina o prodotto "
    "correlato è progettato per funzionare con livelli variabili di autonomia. La valutazione del rischio e la "
    "riduzione del rischio comprendono i rischi derivanti dalle interazioni tra macchine che per raggiungere uno "
    "stesso risultato sono disposte e comandate in modo da avere un funzionamento solidale, formando così una "
    "macchina come definita all'articolo 3, punto 1), lettera d).<br><br>"
    "2. Gli obblighi previsti dai requisiti essenziali di sicurezza e di tutela della salute si applicano "
    "soltanto se esiste il pericolo corrispondente per la macchina o il prodotto correlato in questione, allorché "
    "viene utilizzato nelle condizioni previste dal fabbricante o in condizioni anormali prevedibili. Tuttavia, "
    "il principio di integrazione della sicurezza di cui al punto 1.1.2 e gli obblighi relativi alla marcatura "
    "delle macchine o dei prodotti correlati di cui al punto 1.7.3 e alle istruzioni per l'uso di cui al punto "
    "1.7.4 si applicano in ogni caso.<br><br>"
    "3. I requisiti essenziali di sicurezza e di tutela della salute elencati nel presente allegato sono "
    "inderogabili; tuttavia, tenuto conto dello stato dell'arte, gli obiettivi da essi prefissi possono non "
    "essere raggiunti. In tal caso, la macchina o il prodotto correlato, per quanto possibile, deve essere "
    "progettato e costruito per tendere verso tali obiettivi.<br><br>"
    "4. Il presente allegato si articola in sei capi. Il primo capo ha una portata generale e si applica a tutte "
    "le macchine o prodotti correlati. Gli altri capi si riferiscono a taluni tipi di pericoli più specifici. "
    "Tuttavia, è indispensabile esaminare il presente allegato in tutte le sue parti, al fine di essere certi di "
    "soddisfare tutti i pertinenti requisiti essenziali di sicurezza e di tutela della salute. Nel progettare la "
    "macchina o un prodotto correlato si tiene conto dei requisiti contenuti nel primo capo e di quelli elencati "
    "in uno o più degli altri capi, in funzione dei risultati della valutazione del rischio condotta in "
    "conformità del punto 1 dei presenti principi generali. I requisiti essenziali di sicurezza e di tutela della "
    "salute per la tutela dell'ambiente sono applicabili unicamente alle macchine o ai prodotti correlati a di "
    "cui al punto 2.4.<br><br>"
    "5. I presenti principi generali si applicano alla valutazione del rischio effettuata dal fabbricante di "
    "quasi-macchine."
)


def carica(apps, schema_editor):
    Capitolo = apps.get_model("rischi", "CapitoloValutazione")
    if not Capitolo.objects.exists():
        Capitolo.objects.create(titolo="Definizioni", testo=DEFINIZIONI, ordine=10)
        Capitolo.objects.create(titolo="Principi generali", testo=PRINCIPI, ordine=20)


class Migration(migrations.Migration):
    dependencies = [("rischi", "0029_capitoli_valutazione")]
    operations = [migrations.RunPython(carica, migrations.RunPython.noop)]
