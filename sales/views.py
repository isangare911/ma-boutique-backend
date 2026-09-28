from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import models
from django.utils import timezone
from datetime import timedelta

from .models import Sale
from .serializers import SaleSerializer
from accounts.permissions import (
    IsSameShop, CanViewSales, CanEditSales, CanCancelSale,
)


class SaleViewSet(viewsets.ModelViewSet):
    """
    CRUD sur les ventes.

    - Lecture (GET) : OWNER, MANAGER, SELLER, ACCOUNTANT
    - Création (POST) : OWNER, MANAGER, SELLER
    - Annulation : OWNER, MANAGER
    """
    serializer_class = SaleSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewSales]
        elif self.action == 'cancel':
            classes = [IsAuthenticated, IsSameShop, CanCancelSale]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditSales]
        return [c() for c in classes]

    def get_queryset(self):
        qs = Sale.objects.filter(shop=self.request.user.shop)

        period = self.request.query_params.get('period')
        now = timezone.now()

        if period == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            qs = qs.filter(created_at__gte=start)
        elif period == 'week':
            qs = qs.filter(created_at__gte=now - timedelta(days=7))
        elif period == 'month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            qs = qs.filter(created_at__gte=start)
        elif period == 'year':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            qs = qs.filter(created_at__gte=start)

        return qs.select_related('customer').prefetch_related('items')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Annule une vente et restaure le stock"""
        sale = self.get_object()

        if sale.status == 'CANCELLED':
            return Response({'error': 'Vente déjà annulée'}, status=400)

        from inventory.models import Product
        for item in sale.items.all():
            if item.product:
                Product.objects.filter(id=item.product.id).update(
                    quantity=models.F('quantity') + item.quantity
                )

        sale.status = 'CANCELLED'
        sale.save()

        return Response(SaleSerializer(sale).data)