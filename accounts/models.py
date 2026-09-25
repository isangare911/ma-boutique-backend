import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


# ═══════════════════════════════════════════════════════════
# MODÈLE SHOP (Boutique)
# ═══════════════════════════════════════════════════════════
class Shop(models.Model):
    """Une boutique (tenant du SaaS)"""
    id = models.CharField(
        max_length=50, primary_key=True, editable=False
    )
    name = models.CharField(max_length=200)
    logo_path = models.CharField(max_length=500, blank=True, null=True)
    currency = models.CharField(max_length=10, default='FCFA')
    address = models.CharField(max_length=500, blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    owner_name = models.CharField(max_length=200, blank=True, null=True)

    # Abonnement SaaS
    subscription_plan = models.CharField(
        max_length=20,
        choices=[
            ('TRIAL', 'Essai gratuit'),
            ('ESSENTIEL', 'Essentiel'),
            ('PRO', 'Pro'),
            ('BUSINESS', 'Business'),
        ],
        default='TRIAL',
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('TRIAL', 'Période d\'essai'),
            ('ACTIVE', 'Actif'),
            ('GRACE_PERIOD', 'Période de grâce'),
            ('EXPIRED', 'Expiré'),
        ],
        default='TRIAL',
    )

    subscription_start = models.DateTimeField(default=timezone.now)
    subscription_end = models.DateTimeField(blank=True, null=True)
    last_payment_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shops'
        verbose_name = 'Boutique'
        verbose_name_plural = 'Boutiques'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Génère un ID unique UNIQUEMENT pour les nouvelles boutiques."""
        # ⚡ Générer un ID SEULEMENT si c'est une nouvelle boutique
        if not self.id:
            self.id = f'SHOP-{uuid.uuid4().hex[:8].upper()}'
        # Sinon, garder l'ID existant tel quel (ne JAMAIS le modifier)
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════
# GESTIONNAIRE D'UTILISATEUR
# ═══════════════════════════════════════════════════════════
class UserManager(BaseUserManager):
    """Gestionnaire personnalisé pour créer users et superusers"""
    
    def create_user(self, phone, password=None, **extra_fields):
        if not phone:
            raise ValueError('Le numéro de téléphone est obligatoire')
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'OWNER')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superuser doit avoir is_staff=True')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superuser doit avoir is_superuser=True')

        return self.create_user(phone, password, **extra_fields)


# ═══════════════════════════════════════════════════════════
# MODÈLE USER (Utilisateur personnalisé)
# ═══════════════════════════════════════════════════════════
class User(AbstractUser):
    """Utilisateur personnalisé — authentification par téléphone"""
    
    ROLE_CHOICES = [
        ('OWNER', 'Propriétaire'),
        ('MANAGER', 'Gérant'),
        ('SELLER', 'Vendeur'),
        ('ACCOUNTANT', 'Comptable'),
    ]
    
    # On désactive username (obligatoire par défaut)
    username = None
    
    phone = models.CharField(
        max_length=30, unique=True, verbose_name='Téléphone'
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='SELLER')
    
    # Lien vers la boutique (multi-tenant)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='users',
        null=True,
        blank=True,
    )

    # Champs obligatoires de Django
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f'{self.phone} ({self.get_full_name() or self.role})'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()
    
    
class Payment(models.Model):
    """Paiement d'abonnement avec code unique sécurisé."""
    
    METHOD_CHOICES = [
        ('ORANGE_MONEY', 'Orange Money'),
        ('WAVE', 'Wave'),
        ('MOOV_MONEY', 'Moov Money'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'En attente de paiement'),
        ('PENDING_REVIEW', 'En attente de validation'),
        ('APPROVED', 'Approuvé'),
        ('REJECTED', 'Rejeté'),
        ('CANCELLED', 'Annulé'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    
    # ⚡ CODE UNIQUE de paiement (anti-fraude)
    payment_code = models.CharField(
        max_length=20,
        unique=True,
        editable=False,
        db_index=True,
        null=True,
        blank=True,
        verbose_name='Code de paiement',
    )
    
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='payments',
    )
    plan = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='PENDING',
    )
    
    # ⚡ Code de transaction fourni par l'utilisateur
    transaction_id = models.CharField(max_length=200, blank=True, null=True)
    
    # ⚡ Numéro du payeur
    payer_phone = models.CharField(max_length=30, blank=True, null=True)
    
    # ⚡ Durée activée
    duration_days = models.IntegerField(default=30)
    
    # ⚡ Validation par le propriétaire
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payments',
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    # ⚡ Notes internes
    notes = models.TextField(blank=True, null=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_code']),
        ]

    def __str__(self):
        return f'{self.payment_code} — {self.plan} — {self.status}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'PAY-{uuid.uuid4().hex[:10].upper()}'
        if not self.payment_code:
            self.payment_code = self._generate_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_code():
        """Génère un code unique au format MB-XXXX-XXXX-XXXX."""
        import random
        import string
        
        while True:
            parts = [
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                for _ in range(3)
            ]
            code = f'MB-{parts[0]}-{parts[1]}-{parts[2]}'
            if not Payment.objects.filter(payment_code=code).exists():
                return code

    @staticmethod
    def get_plan_price(plan):
        """Retourne le prix mensuel du plan."""
        prices = {
            'ESSENTIEL': 5000,
            'PRO': 7500,
            'BUSINESS': 10000,
        }
        return prices.get(plan, 0) 

class ShopUser(models.Model):
    """Lien entre un User et une Shop avec un rôle spécifique."""
    
    ROLE_CHOICES = [
        ('OWNER', 'Propriétaire'),
        ('MANAGER', 'Gérant'),
        ('SELLER', 'Vendeur'),
        ('ACCOUNTANT', 'Comptable'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name='members',
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shop_memberships',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='SELLER')
    is_active = models.BooleanField(default=True)
    
    # Permissions spécifiques (JSON personnalisable)
    permissions = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_users'
        unique_together = [['shop', 'user']]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.phone} @ {self.shop.name} ({self.role})'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'MEM-{uuid.uuid4().hex[:8].upper()}'
        super().save(*args, **kwargs)
    