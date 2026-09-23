from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Product
from .serializers import ProductSerializer
from accounts.permissions import IsSameShop


class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD complet sur les produits.
    
    - GET /products/ — Liste des produits
    - POST /products/ — Créer un produit
    - GET /products/{id}/ — Détail
    - PUT/PATCH /products/{id}/ — Modifier
    - DELETE /products/{id}/ — Supprimer
    - GET /products/?category=... — Filtre par catégorie
    - GET /products/?search=... — Recherche par nom
    - GET /products/?low_stock=true — Produits en rupture ou stock faible
    """
    serializer_class = ProductSerializer
    permission_classes = [IsAuthenticated, IsSameShop]

    def get_queryset(self):
        qs = Product.objects.filter(shop=self.request.user.shop)
        
        # Recherche
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        
        # Filtre catégorie
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        
        # Filtre rupture / stock faible
        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            from django.db.models import F
            qs = qs.filter(quantity__lte=F('alert_threshold'))
        
        return qs

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user.shop)