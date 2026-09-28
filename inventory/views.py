from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Product
from .serializers import ProductSerializer
from accounts.permissions import IsSameShop, CanViewStock, CanEditStock


class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD sur les produits.

    - Lecture (GET) : OWNER, MANAGER, SELLER
    - Écriture (POST/PUT/PATCH/DELETE) : OWNER, MANAGER
    """
    serializer_class = ProductSerializer

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewStock]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditStock]
        return [c() for c in classes]

    def get_queryset(self):
        qs = Product.objects.filter(shop=self.request.user.shop)

        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)

        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        low_stock = self.request.query_params.get('low_stock')
        if low_stock == 'true':
            from django.db.models import F
            qs = qs.filter(quantity__lte=F('alert_threshold'))

        return qs

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user.shop)