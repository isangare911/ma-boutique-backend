from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
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