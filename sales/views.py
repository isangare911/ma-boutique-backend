from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta

from .models import Sale
from .serializers import SaleSerializer
from accounts.permissions import (
    IsSameShop, CanViewSales, CanEditSales, CanCancelSale,
)


def _user_has_shop(request):
    return bool(getattr(request.user, 'shop', None))


class SaleViewSet(viewsets.ModelViewSet):
    """
    CRUD sur les ventes.

    - Lecture (GET) : OWNER, MANAGER, SELLER, ACCOUNTANT
    - Création (POST) : OWNER, MANAGER, SELLER
    - Annulation : OWNER, MANAGER
    """
    serializer_class = SaleSerializer
    http_method_names = ['get', 'post', 'head', 'options']  # ⚡ PATCH retiré

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewSales]
        elif self.action == 'cancel':
            classes = [IsAuthenticated, IsSameShop, CanCancelSale]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditSales]
        return [c() for c in classes]

    def get_queryset(self):
        # ⚡ Garde-fou
        if not _user_has_shop(self.request):
            return Sale.objects.none()

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
    @transaction.atomic
    def cancel(self, request, pk=None):
        """Annule une vente et restaure le stock"""
        sale = self.get_object()

        if sale.status == 'CANCELLED':
            return Response({'error': 'Vente déjà annulée'}, status=400)

        # ⚡ Verrouiller la vente
        sale = Sale.objects.select_for_update().get(id=sale.id)

        from inventory.models import Product

        for item in sale.items.all():
            if item.product:
                # ⚡ Vérifier que le produit appartient à la boutique (défense en profondeur)
                Product.objects.filter(
                    id=item.product.id,
                    shop=sale.shop,  # ⚡ filtre de sécurité
                ).update(quantity=F('quantity') + item.quantity)

        sale.status = 'CANCELLED'
        sale.save()

        return Response(SaleSerializer(sale).data)