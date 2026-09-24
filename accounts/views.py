from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Shop
from .serializers import (
    UserSerializer, ShopSerializer, RegisterSerializer, LoginSerializer
)
from .mobile_money_service import MobileMoneyService
from .serializers import PaymentSerializer
from .models import Payment

def get_tokens_for_user(user):
    """Génère access + refresh tokens pour un utilisateur"""
    refresh = RefreshToken.for_user(user)
    # Ajouter des claims personnalisés
    refresh['role'] = user.role
    refresh['shop_id'] = user.shop_id if user.shop else None
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class RegisterView(APIView):
    """POST /api/v1/auth/register/ — Créer une boutique + compte propriétaire"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        tokens = get_tokens_for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens,
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """POST /api/v1/auth/login/ — Connexion par téléphone + mot de passe"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        tokens = get_tokens_for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens,
        })


class MeView(APIView):
    """GET /api/v1/auth/me/ — Profil de l'utilisateur connecté"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ShopSettingsView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/v1/shop/ — Paramètres de la boutique"""
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.shop
    
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .subscription_service import SubscriptionService
from .serializers import SubscriptionSerializer, PLANS


class SubscriptionStatusView(APIView):
    """GET /api/v1/subscription/status/ — État de l'abonnement"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = request.user.shop
        if not shop:
            return Response(
                {'error': 'Aucune boutique associée'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Forcer une vérification du statut
        SubscriptionService.check_status(shop)
        shop.refresh_from_db()
        
        return Response(SubscriptionSerializer(shop).data)


class SubscriptionPlansView(APIView):
    """GET /api/v1/subscription/plans/ — Liste des plans"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PLANS)


class SubscriptionActivateView(APIView):
    """POST /api/v1/subscription/activate/ — Activer un plan (test)"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_code = request.data.get('plan')
        duration_days = int(request.data.get('duration_days', 30))

        if plan_code not in ['ESSENTIEL', 'PRO', 'BUSINESS']:
            return Response(
                {'error': 'Plan invalide'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        shop = request.user.shop
        if not shop:
            return Response(
                {'error': 'Aucune boutique associée'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ⚠️ Dans un vrai système, il faudrait vérifier le paiement ici
        SubscriptionService.activate_plan(shop, plan_code, duration_days)
        
        return Response(SubscriptionSerializer(shop).data)
    
# ═══════════════════════════════════════════════════════════
# MOBILE MONEY (USSD manuel)
# ═══════════════════════════════════════════════════════════

class CreatePaymentView(APIView):
    """
    POST /api/v1/payments/create/
    Body: {"plan": "PRO", "method": "ORANGE_MONEY", "payer_phone": "+223..."}
    
    Crée une demande de paiement et retourne les instructions USSD.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan = request.data.get('plan')
        method = request.data.get('method')
        payer_phone = request.data.get('payer_phone')

        if not plan or not method:
            return Response(
                {'error': 'Plan et méthode requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if plan not in ['ESSENTIEL', 'PRO', 'BUSINESS']:
            return Response(
                {'error': 'Plan invalide'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if method not in ['ORANGE_MONEY', 'WAVE', 'MOOV_MONEY']:
            return Response(
                {'error': 'Méthode de paiement invalide'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.shop:
            return Response(
                {'error': 'Aucune boutique associée'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = MobileMoneyService.create_payment(
                shop=request.user.shop,
                plan=plan,
                method=method,
                payer_phone=payer_phone,
            )
            instructions = MobileMoneyService.get_payment_instructions(payment)

            return Response({
                'payment': PaymentSerializer(payment).data,
                'instructions': instructions,
            }, status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ConfirmPaymentView(APIView):
    """
    POST /api/v1/payments/<payment_id>/confirm/
    Body: {"transaction_id": "MP240924.1234.A5B8C2"}
    
    Confirme un paiement et active l'abonnement.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        transaction_id = request.data.get('transaction_id', '').strip()

        if not transaction_id:
            return Response(
                {'error': 'Code de transaction requis'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(transaction_id) < 4:
            return Response(
                {'error': 'Code de transaction trop court (minimum 4 caractères)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = MobileMoneyService.confirm_payment(
                payment_id=payment_id,
                transaction_id=transaction_id,
                user=request.user,
            )

            # Recharger la boutique mise à jour
            shop = request.user.shop
            shop.refresh_from_db()

            return Response({
                'payment': PaymentSerializer(payment).data,
                'subscription': SubscriptionSerializer(shop).data,
                'message': '✓ Paiement confirmé, abonnement activé !',
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CancelPaymentView(APIView):
    """POST /api/v1/payments/<payment_id>/cancel/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        try:
            payment = MobileMoneyService.cancel_payment(payment_id, request.user)
            return Response(PaymentSerializer(payment).data)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class PaymentListView(APIView):
    """GET /api/v1/payments/ — Historique des paiements"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.shop:
            return Response([])
        payments = MobileMoneyService.get_shop_payments(request.user.shop)
        return Response(PaymentSerializer(payments, many=True).data)
    
# ═══════════════════════════════════════════════════════════
# VUES ADMIN (Dashboard propriétaire)
# ═══════════════════════════════════════════════════════════

class AdminStatsView(APIView):
    """GET /api/v1/admin/stats/ — Statistiques globales"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response(
                {'error': 'Accès réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        stats = MobileMoneyService.get_admin_stats()
        return Response(stats)


class AdminShopsView(APIView):
    """GET /api/v1/admin/shops/ — Liste des boutiques"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response(
                {'error': 'Accès réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        shops = MobileMoneyService.get_all_shops_with_stats()
        return Response(shops)


class AdminPaymentsView(APIView):
    """GET /api/v1/admin/payments/ — Liste des paiements"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response(
                {'error': 'Accès réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        status_filter = request.query_params.get('status')
        payments = MobileMoneyService.get_all_payments(status_filter)
        return Response(PaymentSerializer(payments, many=True).data)


class AdminApprovePaymentView(APIView):
    """POST /api/v1/admin/payments/<payment_id>/approve/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        if not request.user.is_superuser:
            return Response(
                {'error': 'Accès réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            payment = MobileMoneyService.approve_payment(payment_id, request.user)
            return Response({
                'payment': PaymentSerializer(payment).data,
                'message': f'✓ Paiement {payment.payment_code} approuvé',
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )


class AdminRejectPaymentView(APIView):
    """POST /api/v1/admin/payments/<payment_id>/reject/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        if not request.user.is_superuser:
            return Response(
                {'error': 'Accès réservé aux administrateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        reason = request.data.get('reason', '').strip()
        if not reason:
            return Response(
                {'error': 'Raison du rejet requise'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payment = MobileMoneyService.reject_payment(
                payment_id, reason, request.user
            )
            return Response({
                'payment': PaymentSerializer(payment).data,
                'message': f'Paiement {payment.payment_code} rejeté',
            })
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )