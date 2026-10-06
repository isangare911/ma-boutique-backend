from django.urls import path
from .views import SyncView, SyncStatusView, SyncFullView

app_name = 'sync'

urlpatterns = [
    path('sync/', SyncView.as_view(), name='sync'),
    path('sync/status/', SyncStatusView.as_view(), name='sync-status'),
    path('sync/full/', SyncFullView.as_view(), name='sync-full'), 
]