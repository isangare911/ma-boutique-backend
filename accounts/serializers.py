from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Shop
from .models import Payment


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
            'shop', 'is_active', 'is_superuser', 'is_staff', 'date_joined',
        ]
        read_only_fields = ['id', 'date_joined', 'is_superuser', 'is_staff']


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
    
from .subscription_service import SubscriptionService


class SubscriptionSerializer(serializers.ModelSerializer):
    days_remaining = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        fields = [
            'id', 'subscription_plan', 'subscription_status',
            'subscription_start', 'subscription_end',
            'days_remaining', 'is_active', 'last_payment_date',
        ]

    def get_days_remaining(self, obj):
        return SubscriptionService.get_days_remaining(obj)

    def get_is_active(self, obj):
        return SubscriptionService.is_active(obj)


class SubscriptionPlanSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    price_monthly = serializers.IntegerField()
    price_yearly = serializers.IntegerField()
    features = serializers.ListField(child=serializers.CharField())


# ═══════════════════════════════════════════════════════════
# LISTE DES PLANS DISPONIBLES
# ═══════════════════════════════════════════════════════════
PLANS = [
    {
        'code': 'ESSENTIEL',
        'name': 'Essentiel',
        'price_monthly': 5000,
        'price_yearly': 50000,
        'features': [
            'Ventes illimitées',
            'Gestion du stock',
            'Cahier de crédit',
            'Notifications',
            'Synchronisation Cloud',
            '1 utilisateur',
        ],
    },
    {
        'code': 'PRO',
        'name': 'Pro',
        'price_monthly': 7500,
        'price_yearly': 75000,
        'features': [
            'Tout Essentiel +',
            'Gestion de la caisse',
            'Gestion des dépenses',
            'Rapports avancés',
            'Export Excel/PDF',
            'Support prioritaire',
        ],
    },
    {
        'code': 'BUSINESS',
        'name': 'Business',
        'price_monthly': 10000,
        'price_yearly': 100000,
        'features': [
            'Tout Pro +',
            'Gestion des fournisseurs',
            'Multi-utilisateurs (5)',
            'Multi-boutiques',
            'Statistiques avancées',
            'Support dédié',
        ],
    },
]

class PaymentSerializer(serializers.ModelSerializer):
    plan_name = serializers.SerializerMethodField()
    method_name = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            'id',
            'payment_code',
            'plan',
            'plan_name',
            'amount',
            'method',
            'method_name',
            'status',
            'transaction_id',
            'payer_phone',
            'duration_days',
            'created_at',
            'approved_at',       # ⚡ Remplacé (était paid_at)
            'rejection_reason',
            'approved_by',
        ]
        read_only_fields = ['created_at', 'approved_at']

    def get_plan_name(self, obj):
        names = {
            'ESSENTIEL': 'Essentiel',
            'PRO': 'Pro',
            'BUSINESS': 'Business',
        }
        return names.get(obj.plan, obj.plan)

    def get_method_name(self, obj):
        names = {
            'ORANGE_MONEY': 'Orange Money',
            'WAVE': 'Wave',
            'MOOV_MONEY': 'Moov Money',
            'CASH': 'Espèces',
        }
        return names.get(obj.method, obj.method)