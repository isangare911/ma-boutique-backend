from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from ma_boutique.views import healthz, readyz


urlpatterns = [
    # ═══════════════════════════════════════════════════════
    # HEALTHCHECK
    # ═══════════════════════════════════════════════════════
    path('healthz/', healthz, name='healthz'),   # liveness
    path('readyz/', readyz, name='readyz'),      # readiness (DB)

    # ═══════════════════════════════════════════════════════
    # ADMIN
    # ═══════════════════════════════════════════════════════
    path('admin/', admin.site.urls),

    # ═══════════════════════════════════════════════════════
    # API v1
    # ═══════════════════════════════════════════════════════
    path('api/v1/', include('accounts.urls')),
    path('api/v1/', include('inventory.urls')),
    path('api/v1/', include('sales.urls')),
    path('api/v1/', include('customers.urls')),
    path('api/v1/', include('finance.urls')),
    path('api/v1/', include('sync.urls')),
]

# En dev : servir les médias et statiques
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)