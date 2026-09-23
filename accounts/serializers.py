from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Shop


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = [
            'id', 'name', 'logo_path', 'currency', 'address', 'phone',
            'email', 'owner_name', 'subscription_plan', 'subscription_start',
            'subscription_end', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    shop = ShopSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id', 'phone', 'first_name', 'last_name', 'role',
            'shop', 'is_active', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined']


class RegisterSerializer(serializers.Serializer):
    """Inscription : crée une boutique + un propriétaire"""
    # Utilisateur
    phone = serializers.CharField(max_length=30)
    password = serializers.CharField(min_length=6, write_only=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    
    # Boutique
    shop_name = serializers.CharField(max_length=200)
    currency = serializers.CharField(max_length=10, default='FCFA')

    def validate_phone(self, value):
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                'Ce numéro de téléphone est déjà utilisé.'
            )
        return value

    def create(self, validated_data):
        # Créer la boutique
        shop = Shop.objects.create(
            name=validated_data['shop_name'],
            currency=validated_data.get('currency', 'FCFA'),
            owner_name=f"{validated_data.get('first_name', '')} {validated_data.get('last_name', '')}".strip(),
        )
        
        # Créer l'utilisateur propriétaire
        user = User.objects.create_user(
            phone=validated_data['phone'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            role='OWNER',
            shop=shop,
        )
        
        return user


class LoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=30)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            request=self.context.get('request'),
            phone=data['phone'],
            password=data['password'],
        )
        if not user:
            raise serializers.ValidationError('Identifiants invalides.')
        if not user.is_active:
            raise serializers.ValidationError('Ce compte est désactivé.')
        
        data['user'] = user
        return data