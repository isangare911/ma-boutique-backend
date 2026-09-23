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