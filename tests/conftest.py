"""
Fixtures partagées pour tous les tests.

Stratégie :
- Chaque test tourne dans une transaction Postgres → rollback auto.
- Le cache DRF (throttling) est vidé entre chaque test.
- Deux boutiques isolées (A et B) pour tester le multi-tenant.
"""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.models import User, Shop, ShopUser
from customers.models import Customer, Credit
from inventory.models import Product


# ═══════════════════════════════════════════════════════════
# NETTOYAGE AUTOMATIQUE
# ═══════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clear_cache():
    """
    Vide le cache DRF avant ET après chaque test.
    Empêche les fuites de throttling entre tests.
    """
    cache.clear()
    yield
    cache.clear()


# ═══════════════════════════════════════════════════════════
# BOUTIQUES
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def shop_a(db):
    return Shop.objects.create(name='Boutique A', currency='FCFA')


@pytest.fixture
def shop_b(db):
    return Shop.objects.create(name='Boutique B', currency='FCFA')


# ═══════════════════════════════════════════════════════════
# UTILISATEURS
# ═══════════════════════════════════════════════════════════

def _create_user_with_membership(phone, password, shop, role):
    user = User.objects.create_user(
        phone=phone,
        password=password,
        role=role,
        shop=shop,
    )
    ShopUser.objects.create(shop=shop, user=user, role=role)
    return user


@pytest.fixture
def owner_a(shop_a):
    return _create_user_with_membership(
        phone='+22370000001',
        password='MotDePasse123!',
        shop=shop_a,
        role='OWNER',
    )


@pytest.fixture
def owner_b(shop_b):
    return _create_user_with_membership(
        phone='+22370000002',
        password='MotDePasse123!',
        shop=shop_b,
        role='OWNER',
    )


@pytest.fixture
def seller_a(shop_a):
    return _create_user_with_membership(
        phone='+22370000003',
        password='MotDePasse123!',
        shop=shop_a,
        role='SELLER',
    )


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        phone='+22379999999',
        password='SuperAdmin123!',
    )


# ═══════════════════════════════════════════════════════════
# CLIENTS API AUTHENTIFIÉS
# ═══════════════════════════════════════════════════════════

def _auth_client(user):
    """Retourne un APIClient avec un JWT valide dans le header."""
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    return client


@pytest.fixture
def client_a(owner_a):
    return _auth_client(owner_a)


@pytest.fixture
def client_b(owner_b):
    return _auth_client(owner_b)


@pytest.fixture
def client_seller_a(seller_a):
    return _auth_client(seller_a)


@pytest.fixture
def client_superuser(superuser):
    return _auth_client(superuser)


@pytest.fixture
def anon_client():
    """Client non authentifié."""
    return APIClient()


# ═══════════════════════════════════════════════════════════
# DONNÉES MÉTIER
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def product_a(shop_a):
    return Product.objects.create(
        shop=shop_a,
        name='Riz 5kg',
        purchase_price=4000,
        selling_price=5000,
        quantity=20,
    )


@pytest.fixture
def product_b(shop_b):
    return Product.objects.create(
        shop=shop_b,
        name='Huile 1L',
        purchase_price=800,
        selling_price=1000,
        quantity=50,
    )


@pytest.fixture
def customer_a(shop_a):
    return Customer.objects.create(shop=shop_a, name='Client A')


@pytest.fixture
def customer_b(shop_b):
    return Customer.objects.create(shop=shop_b, name='Client B')


@pytest.fixture
def credit_b(shop_b, customer_b):
    """Un crédit appartenant à la boutique B (pour les tests cross-tenant)."""
    from django.utils import timezone
    from datetime import timedelta

    return Credit.objects.create(
        shop=shop_b,
        customer=customer_b,
        total_amount=10000,
        due_date=timezone.now() + timedelta(days=30),
    )