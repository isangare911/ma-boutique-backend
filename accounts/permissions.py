from rest_framework import permissions
from .models import ShopUser


# ═══════════════════════════════════════════════════════════
# HELPER : rôle de l'utilisateur dans sa boutique
# ═══════════════════════════════════════════════════════════

def get_user_role(user):
    """
    Retourne le rôle de l'utilisateur dans sa boutique.
    - superuser → 'OWNER' (bypass admin SaaS)
    - sinon → ShopUser.role du shop courant
    - fallback User.role UNIQUEMENT si aucune ShopUser n'existe (legacy)
    """
    if not user or not user.is_authenticated:
        return None

    if user.is_superuser:
        return 'OWNER'

    if not user.shop_id:
        return None

    member = ShopUser.objects.filter(
        shop_id=user.shop_id,
        user=user,
        is_active=True,
    ).only('role').first()

    if member:
        return member.role

    # ⚡ Fallback UNIQUEMENT si l'utilisateur n'a AUCUNE membership (legacy pur)
    if not ShopUser.objects.filter(user=user).exists():
        return getattr(user, 'role', None)

    # ⚡ L'utilisateur a des memberships mais inactives → aucun rôle
    return None


# ═══════════════════════════════════════════════════════════
# PERMISSION SUPERUSER (centralisée)
# ═══════════════════════════════════════════════════════════

class IsSuperUser(permissions.BasePermission):
    """Autorise uniquement les superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


# ═══════════════════════════════════════════════════════════
# IS_SAME_SHOP
# ═══════════════════════════════════════════════════════════

class IsSameShop(permissions.BasePermission):
    """Autorise uniquement si l'objet appartient à la boutique de l'utilisateur."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        if hasattr(obj, 'shop'):
            return obj.shop_id == request.user.shop_id
        if hasattr(obj, 'id') and obj.__class__.__name__ == 'Shop':
            return obj.id == request.user.shop_id
        return False


# ═══════════════════════════════════════════════════════════
# BASE : vérifier un rôle
# ═══════════════════════════════════════════════════════════

class HasAnyRole(permissions.BasePermission):
    """Vérifie que l'utilisateur a l'un des rôles autorisés."""
    allowed_roles = ()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        role = get_user_role(request.user)
        return role in self.allowed_roles


# ═══════════════════════════════════════════════════════════
# PERMISSIONS PAR MODULE
# ═══════════════════════════════════════════════════════════

# ─── Utilisateurs ───────────────────────────────────────────
class IsOwner(HasAnyRole):
    allowed_roles = ('OWNER',)

class IsOwnerOrManager(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER')


# ─── Ventes ─────────────────────────────────────────────────
class CanViewSales(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER', 'ACCOUNTANT')

class CanEditSales(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER')

class CanCancelSale(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER')


# ─── Stock ──────────────────────────────────────────────────
class CanViewStock(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER')

class CanEditStock(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER')


# ─── Crédits ────────────────────────────────────────────────
class CanViewCredits(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER', 'ACCOUNTANT')

class CanEditCredits(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER')

class CanCollectCreditPayment(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER', 'ACCOUNTANT')


# ─── Clients ────────────────────────────────────────────────
class CanViewCustomers(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER', 'ACCOUNTANT')

class CanEditCustomers(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'SELLER')


# ─── Caisse / Dépenses ──────────────────────────────────────
class CanViewCash(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'ACCOUNTANT')

class CanEditCash(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'ACCOUNTANT')


# ─── Fournisseurs ───────────────────────────────────────────
class CanViewSuppliers(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER')

class CanEditSuppliers(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER')


# ─── Rapports ───────────────────────────────────────────────
class CanViewReports(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER', 'ACCOUNTANT')


# ─── Sync ───────────────────────────────────────────────────
class CanUseSync(HasAnyRole):
    allowed_roles = ('OWNER', 'MANAGER')