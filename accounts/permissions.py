from rest_framework import permissions


class IsSameShop(permissions.BasePermission):
    """
    Autorise l'accès uniquement si l'objet appartient à la boutique
    de l'utilisateur connecté.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin : accès total
        if request.user.is_superuser:
            return True
        
        # Vérifier que l'objet a un shop et qu'il correspond
        if hasattr(obj, 'shop'):
            return obj.shop_id == request.user.shop_id
        
        # Si l'objet est un shop lui-même
        if hasattr(obj, 'id') and obj.__class__.__name__ == 'Shop':
            return obj.id == request.user.shop_id
        
        return False