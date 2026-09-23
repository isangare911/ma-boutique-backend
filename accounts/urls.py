from django.urls import path
from .views import RegisterView, LoginView, MeView, ShopSettingsView

app_name = 'accounts'

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('shop/', ShopSettingsView.as_view(), name='shop-settings'),
]