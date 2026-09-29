from django.urls import path

from .views import (
    # Auth
    RegisterView, LoginView, MeView, ShopSettingsView,
    
    # Abonnement
    SubscriptionStatusView, SubscriptionPlansView, SubscriptionActivateView,
    
    # Paiements (client)
    CreatePaymentView, SubmitPaymentProofView,
    CancelPaymentView, PaymentListView,
    
    # Admin (propriétaire)
    AdminStatsView, AdminShopsView, AdminPaymentsView,
    AdminApprovePaymentView, AdminRejectPaymentView,
    ShopUserListView, ShopUserDetailView, AdminShopPaymentsView,
    RequestOTPView, VerifyOTPView, ChangePasswordView,
    GrantTrialView,
    CancelSubscriptionView,
    ReactivateShopView,
)

app_name = 'accounts'

urlpatterns = [
    # ═══════════════════════════════════════════════════════
    # AUTHENTIFICATION
    # ═══════════════════════════════════════════════════════
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('shop/', ShopSettingsView.as_view(), name='shop-settings'),

    # ═══════════════════════════════════════════════════════
    # ABONNEMENT
    # ═══════════════════════════════════════════════════════
    path('subscription/status/', SubscriptionStatusView.as_view(), name='sub-status'),
    path('subscription/plans/', SubscriptionPlansView.as_view(), name='sub-plans'),
    path('subscription/activate/', SubscriptionActivateView.as_view(), name='sub-activate'),
    
    # Multi-utilisateurs
    path('shop/users/', ShopUserListView.as_view(), name='shop-users'),
    path('shop/users/<str:member_id>/', ShopUserDetailView.as_view(), name='shop-user-detail'),

    # ═══════════════════════════════════════════════════════
    # PAIEMENTS (client)
    # ═══════════════════════════════════════════════════════
    path('payments/', PaymentListView.as_view(), name='payments-list'),
    path('payments/create/', CreatePaymentView.as_view(), name='payment-create'),
    
    # ⚡ NOUVELLE ROUTE : Soumettre la preuve
    path(
        'payments/<str:payment_id>/submit/',
        SubmitPaymentProofView.as_view(),
        name='payment-submit',
    ),
    
    path('auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    
    path(
        'payments/<str:payment_id>/cancel/',
        CancelPaymentView.as_view(),
        name='payment-cancel',
    ),
    path('auth/request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('auth/verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),

    # ═══════════════════════════════════════════════════════
    # ADMIN (propriétaire de l'app)
    # ═══════════════════════════════════════════════════════
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
    path('admin/shops/', AdminShopsView.as_view(), name='admin-shops'),
    path('admin/payments/', AdminPaymentsView.as_view(), name='admin-payments'),
    path(
        'admin/payments/<str:payment_id>/approve/',
        AdminApprovePaymentView.as_view(),
        name='admin-approve',
    ),
    path(
        'admin/payments/<str:payment_id>/reject/',
        AdminRejectPaymentView.as_view(),
        name='admin-reject',
    ),
    path(
    'admin/shops/<str:shop_id>/payments/',
    AdminShopPaymentsView.as_view(),
    name='admin-shop-payments',
    ),
    
    path(
    'admin/shops/<str:shop_id>/grant-trial/',
    GrantTrialView.as_view(),
    name='admin-grant-trial',
    ),
    path(
        'admin/shops/<str:shop_id>/cancel-subscription/',
        CancelSubscriptionView.as_view(),
        name='admin-cancel-subscription',
    ),
    path(
        'admin/shops/<str:shop_id>/reactivate/',
        ReactivateShopView.as_view(),
        name='admin-reactivate-shop',
    ),
]