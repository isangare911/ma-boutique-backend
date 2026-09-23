from django.urls import path
from .views import SyncView, SyncStatusView

app_name = 'sync'

urlpatterns = [
    path('sync/', SyncView.as_view(), name='sync'),
    path('sync/status/', SyncStatusView.as_view(), name='sync-status'),
]