from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

admin.site.site_header = "Cosmap – Analisi dei rischi"
admin.site.site_title = "Analisi dei rischi"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accesso/", auth_views.LoginView.as_view(template_name="rischi/login.html"), name="login"),
    path("uscita/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("rischi.urls")),
]

# Con il server di sviluppo mostra anche i file caricati (es. il logo del fabbricante)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
