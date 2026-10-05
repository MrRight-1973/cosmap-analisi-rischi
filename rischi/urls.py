from django.urls import path

from . import views

urlpatterns = [
    path("", views.elenco_commesse, name="elenco_commesse"),
    path("commesse/nuova/", views.nuova_commessa, name="nuova_commessa"),
    path("analisi/<int:pk>/", views.analisi, name="analisi"),
    path("analisi/<int:pk>/rev/<int:numero>/", views.analisi, name="analisi_revisione"),
    path("revisioni/<int:revisione_pk>/applicabilita/", views.applicabilita, name="applicabilita"),
    path("revisioni/<int:revisione_pk>/nuova-scheda/", views.nuova_scheda, name="nuova_scheda"),
    path("revisioni/<int:pk>/azione/<slug:azione>/", views.azione_revisione, name="azione_revisione"),
    path("schede/<int:pk>/", views.scheda, name="scheda"),
    path("schede/<int:pk>/conferma/", views.decisione_rapida, name="conferma_scheda"),
    path("macchine/<int:pk>/", views.macchina, name="macchina"),
    path("revisioni/<int:pk>/documenti/<slug:tipo>/", views.genera_documento, name="genera_documento"),
    path("documenti/<int:pk>/", views.scarica_documento, name="scarica_documento"),
    path("registro/", views.registro, name="registro"),
]
