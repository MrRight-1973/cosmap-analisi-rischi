from django.urls import path

from . import views

urlpatterns = [
    path("", views.elenco_commesse, name="elenco_commesse"),
    path("commesse/nuova/", views.nuova_commessa, name="nuova_commessa"),
    path("commesse/<int:pk>/elimina/", views.elimina_commessa, name="elimina_commessa"),
    path("analisi/<int:pk>/", views.analisi, name="analisi"),
    path("analisi/<int:pk>/rev/<int:numero>/", views.analisi, name="analisi_revisione"),
    path("revisioni/<int:revisione_pk>/applicabilita/", views.applicabilita, name="applicabilita"),
    path("revisioni/<int:revisione_pk>/nuova-scheda/", views.nuova_scheda, name="nuova_scheda"),
    path("revisioni/<int:pk>/azione/<slug:azione>/", views.azione_revisione, name="azione_revisione"),
    path("schede/<int:pk>/", views.scheda, name="scheda"),
    path("schede/<int:pk>/conferma/", views.decisione_rapida, name="conferma_scheda"),
    path("schede/<int:pk>/da-modello/", views.aggiorna_da_modello, name="aggiorna_da_modello"),
    path("schede/<int:pk>/allegati/", views.aggiungi_allegato, name="aggiungi_allegato"),
    path("allegati/<int:pk>/elimina/", views.elimina_allegato, name="elimina_allegato"),
    path("revisioni/<int:revisione_pk>/nuova-funzione/", views.nuova_funzione, name="nuova_funzione"),
    path("funzioni/<int:pk>/", views.funzione, name="funzione"),
    path("funzioni/<int:pk>/elimina/", views.elimina_funzione, name="elimina_funzione"),
    path("funzioni/<int:pk>/calcolo/", views.valutazione_funzione, name="valutazione_funzione"),
    path("funzioni/<int:pk>/prove/", views.prove_funzione, name="prove_funzione"),
    path("revisioni/<int:pk>/validazione/", views.validazione, name="validazione"),
    path("revisioni/<int:pk>/validazione/<slug:azione>/", views.azione_validazione, name="azione_validazione"),
    path("articoli-sicurezza.json", views.articoli_sicurezza, name="articoli_sicurezza"),
    path("macchine/<int:pk>/", views.macchina, name="macchina"),
    path("revisioni/<int:pk>/documenti/<slug:tipo>/", views.genera_documento, name="genera_documento"),
    path("documenti/<int:pk>/", views.scarica_documento, name="scarica_documento"),
    path("registro/", views.registro, name="registro"),
]
