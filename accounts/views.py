from rest_framework import status, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from .models import User, Shop
from .serializers import (
    UserSerializer, ShopSerializer, RegisterSerializer, LoginSerializer
)


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