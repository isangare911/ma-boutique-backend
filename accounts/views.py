from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from datetime import timedelta

from .models import User, Shop, Payment, ShopUser
from .serializers import (
    UserSerializer, ShopSerializer, RegisterSerializer, LoginSerializer,
    PaymentSerializer, SubscriptionSerializer, PLANS,
    ShopUserSerializer, AddShopUserSerializer, ChangePasswordSerializer,
    generate_secure_password, GrantTrialSerializer, CancelSubscriptionSerializer,
)
from .subscription_service import SubscriptionService
from .mobile_money_service import MobileMoneyService
from accounts.permissions import get_user_role, IsSuperUser


# ═══════════════════════════════════════════════════════════
# THROTTLES
# ═══════════════════════════════════════════════════════════

class LoginThrottle(AnonRateThrottle):
    scope = 'login'


class RegisterThrottle(AnonRateThrottle):
    scope = 'register'


class PaymentCreateThrottle(AnonRateThrottle):
    scope = 'payment_create'


class PaymentSubmitThrottle(AnonRateThrottle):
    scope = 'payment_submit'


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════

def get_tokens_for_user(user):
    """Génère access + refresh tokens pour un utilisateur"""
    refresh = RefreshToken.for_user(user)
    refresh['role'] = user.role
    refresh['shop_id'] = user.shop_id if user.shop else None
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


# ═══════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ═══════════════════════════════════════════════════════════

class RegisterView(APIView):
    """POST /api/v1/auth/register/ — Créer une boutique + propriétaire"""
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

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
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={'request': request},
        )
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
        shop = self.request.user.shop
        if not shop:
            from rest_framework.exceptions import NotFound
            raise NotFound('Aucune boutique associée à ce compte')
        return shop


# ═══════════════════════════════════════════════════════════
# CHANGEMENT DE MOT DE PASSE
# ═══════════════════════════════════════════════════════════

class ChangePasswordView(APIView):
    """
    POST /api/v1/auth/change-password/
    Body: {"old_password": "...", "new_password": "..."}

    Si l'utilisateur a must_change_password=True, old_password n'est pas requis.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        new_password = serializer.validated_data['new_password']
        old_password = serializer.validated_data.get('old_password')

        if not user.must_change_password:
            if not old_password:
                return Response(
                    {'error': 'Ancien mot de passe requis'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not user.check_password(old_password):
                return Response(
                    {'error': 'Ancien mot de passe incorrect'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            validate_password(new_password, user)
        except DjangoValidationError as e:
            return Response(
                {'error': ' '.join(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.must_change_password = False
        user.save(update_fields=['password', 'must_change_password'])

        return Response({
            'success': True,
            'message': 'Mot de passe modifié avec succès',
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


# ═══════════════════════════════════════════════════════════
# ABONNEMENT
# ═══════════════════════════════════════════════════════════

class SubscriptionStatusView(APIView):
    """GET /api/v1/subscription/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = request.user.shop
        if not shop:
            return Response(
                {'error': 'Aucune boutique associée'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        SubscriptionService.check_status(shop)
        shop.refresh_from_db()

        return Response(SubscriptionSerializer(shop).data)


class SubscriptionPlansView(APIView):
    """GET /api/v1/subscription/plans/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(PLANS)


# ═══════════════════════════════════════════════════════════
# MOBILE MONEY
# ═══════════════════════════════════════════════════════════

class CreatePaymentView(APIView):
    """POST /api/v1/payments/create/"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentCreateThrottle]

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


class SubmitPaymentProofView(APIView):
    """POST /api/v1/payments/<payment_id>/submit/"""
    permission_classes = [IsAuthenticated]
    throttle_classes = [PaymentSubmitThrottle]

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
            payment = MobileMoneyService.submit_payment_proof(
                payment_id=payment_id,
                transaction_id=transaction_id,
                user=request.user,
            )

            return Response({
                'payment': PaymentSerializer(payment).data,
                'message': 'Preuve soumise. En attente de validation.',
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
    """GET /api/v1/payments/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.shop:
            return Response([])
        payments = MobileMoneyService.get_shop_payments(request.user.shop)
        return Response(PaymentSerializer(payments, many=True).data)


# ═══════════════════════════════════════════════════════════
# VUES ADMIN — toutes protégées par IsSuperUser
# ═══════════════════════════════════════════════════════════

class AdminStatsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request):
        return Response(MobileMoneyService.get_admin_stats())


class AdminShopsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request):
        return Response(MobileMoneyService.get_all_shops_with_stats())


class AdminPaymentsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request):
        status_filter = request.query_params.get('status')
        payments = MobileMoneyService.get_all_payments(status_filter)
        return Response(PaymentSerializer(payments, many=True).data)


class AdminApprovePaymentView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, payment_id):
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
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, payment_id):
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


class AdminShopPaymentsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Boutique introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        payments = Payment.objects.filter(shop=shop).order_by('-created_at')
        return Response(PaymentSerializer(payments, many=True).data)


# ═══════════════════════════════════════════════════════════
# MULTI-UTILISATEURS PAR BOUTIQUE
# ═══════════════════════════════════════════════════════════

class ShopUserListView(APIView):
    """
    GET /api/v1/shop/users/ — OWNER, MANAGER
    POST /api/v1/shop/users/ — OWNER uniquement
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if get_user_role(request.user) not in ('OWNER', 'MANAGER'):
            return Response(
                {'error': 'Accès refusé'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not request.user.shop:
            return Response([])

        members = ShopUser.objects.filter(
            shop=request.user.shop,
        ).select_related('user')

        serializer = ShopUserSerializer(members, many=True)
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request):
        if get_user_role(request.user) != 'OWNER':
            return Response(
                {'error': 'Seul le propriétaire peut ajouter des utilisateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not request.user.shop:
            return Response(
                {'error': 'Aucune boutique associée'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AddShopUserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone = serializer.validated_data['phone']
        role = serializer.validated_data['role']
        first_name = serializer.validated_data.get('first_name', '')
        last_name = serializer.validated_data.get('last_name', '')
        password = serializer.validated_data.get('password')

        user = User.objects.filter(phone=phone).first()
        generated_password = None

        if not user:
            if not password:
                generated_password = generate_secure_password(10)
                password = generated_password

            user = User.objects.create_user(
                phone=phone,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role,
                shop=request.user.shop,
                must_change_password=True,
            )

        if ShopUser.objects.filter(shop=request.user.shop, user=user).exists():
            return Response(
                {'error': 'Cet utilisateur est déjà membre de la boutique'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        member = ShopUser.objects.create(
            shop=request.user.shop,
            user=user,
            role=role,
        )

        response_data = ShopUserSerializer(member).data
        if generated_password:
            response_data['generated_password'] = generated_password

        return Response(response_data, status=status.HTTP_201_CREATED)


class ShopUserDetailView(APIView):
    """OWNER peut tout, MANAGER peut seulement lire."""
    permission_classes = [IsAuthenticated]

    def get_object(self, request, member_id):
        try:
            return ShopUser.objects.get(id=member_id, shop=request.user.shop)
        except ShopUser.DoesNotExist:
            return None

    def get(self, request, member_id):
        if get_user_role(request.user) not in ('OWNER', 'MANAGER'):
            return Response(
                {'error': 'Accès refusé'},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = self.get_object(request, member_id)
        if not member:
            return Response(
                {'error': 'Membre introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ShopUserSerializer(member).data)

    @transaction.atomic
    def patch(self, request, member_id):
        if get_user_role(request.user) != 'OWNER':
            return Response(
                {'error': 'Seul le propriétaire peut modifier les utilisateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = self.get_object(request, member_id)
        if not member:
            return Response(
                {'error': 'Membre introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if member.role == 'OWNER':
            return Response(
                {'error': 'Impossible de modifier le propriétaire'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_role = request.data.get('role')
        if new_role:
            if new_role not in ['MANAGER', 'SELLER', 'ACCOUNTANT']:
                return Response(
                    {'error': 'Rôle invalide'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            member.role = new_role
            member.user.role = new_role
            member.user.save(update_fields=['role'])

        is_active = request.data.get('is_active')
        if is_active is not None:
            member.is_active = is_active
            # ⚡ Désactiver aussi le User si la membership devient inactive
            if not is_active:
                member.user.is_active = False
                member.user.save(update_fields=['is_active'])

        member.save()
        return Response(ShopUserSerializer(member).data)

    @transaction.atomic
    def delete(self, request, member_id):
        if get_user_role(request.user) != 'OWNER':
            return Response(
                {'error': 'Seul le propriétaire peut supprimer des utilisateurs'},
                status=status.HTTP_403_FORBIDDEN,
            )

        member = self.get_object(request, member_id)
        if not member:
            return Response(
                {'error': 'Membre introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if member.role == 'OWNER':
            return Response(
                {'error': 'Impossible de supprimer le propriétaire'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if member.user == request.user:
            return Response(
                {'error': 'Vous ne pouvez pas vous supprimer vous-même'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ⚡ Nettoyer User.role pour éviter le fallback
        user = member.user
        member.delete()

        if not ShopUser.objects.filter(user=user).exists():
            user.role = 'SELLER'
            user.shop = None
            user.save(update_fields=['role', 'shop'])

        return Response(status=status.HTTP_204_NO_CONTENT)


# ═══════════════════════════════════════════════════════════
# GESTION DES ABONNEMENTS (ADMIN)
# ═══════════════════════════════════════════════════════════

class GrantTrialView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, shop_id):
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Boutique introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = GrantTrialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        days = serializer.validated_data['days']
        plan = serializer.validated_data['plan']

        now = timezone.now()
        shop.subscription_plan = plan
        shop.subscription_status = 'TRIAL'
        shop.subscription_start = now
        shop.subscription_end = now + timedelta(days=days)
        shop.is_active = True
        shop.cancellation_reason = None
        shop.cancelled_at = None
        shop.save()

        return Response({
            'success': True,
            'message': f'Essai de {days} jours accordé ({plan})',
            'shop': ShopSerializer(shop).data,
        }, status=status.HTTP_200_OK)


class CancelSubscriptionView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, shop_id):
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Boutique introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = CancelSubscriptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data['reason']

        shop.subscription_status = 'CANCELLED'
        shop.is_active = False
        shop.cancellation_reason = reason
        shop.cancelled_at = timezone.now()
        shop.save()

        return Response({
            'success': True,
            'message': f'Abonnement annulé : {reason}',
            'shop': ShopSerializer(shop).data,
        }, status=status.HTTP_200_OK)


class ReactivateShopView(APIView):
    permission_classes = [IsAuthenticated, IsSuperUser]

    def post(self, request, shop_id):
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return Response(
                {'error': 'Boutique introuvable'},
                status=status.HTTP_404_NOT_FOUND,
            )

        days = int(request.data.get('days', 30))

        now = timezone.now()
        shop.subscription_status = 'ACTIVE'
        shop.subscription_start = now
        shop.subscription_end = now + timedelta(days=days)
        shop.is_active = True
        shop.cancellation_reason = None
        shop.cancelled_at = None
        shop.save()

        return Response({
            'success': True,
            'message': f'Boutique réactivée pour {days} jours',
            'shop': ShopSerializer(shop).data,
        }, status=status.HTTP_200_OK)