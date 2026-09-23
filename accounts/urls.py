from django.urls import path
from .views import (
    RegisterView, LoginView, MeView, ShopSettingsView,
    SubscriptionStatusView, SubscriptionPlansView, SubscriptionActivateView,)

app_name = 'accounts'

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('shop/', ShopSettingsView.as_view(), name='shop-settings'),
    path('subscription/status/', SubscriptionStatusView.as_view(), name='sub-status'),
    path('subscription/plans/', SubscriptionPlansView.as_view(), name='sub-plans'),
    path('subscription/activate/', SubscriptionActivateView.as_view(), name='sub-activate'),
]