from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum
from django.utils import timezone

from .models import (
    CashSession, CashMovement, Expense, Supplier, SupplierTransaction
)
from .serializers import (
    CashSessionSerializer, CashMovementSerializer,
    ExpenseSerializer, SupplierSerializer, SupplierTransactionSerializer
)
from accounts.permissions import (
    IsSameShop, CanViewCash, CanEditCash,
    CanViewSuppliers, CanEditSuppliers,
)


class CashSessionViewSet(viewsets.ModelViewSet):
    """
    Caisse : OWNER, MANAGER, ACCOUNTANT (lecture et écriture)
    """
    serializer_class = CashSessionSerializer
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewCash]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditCash]
        return [c() for c in classes]

    def get_queryset(self):
        return CashSession.objects.filter(shop=self.request.user.shop)

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user.shop)

    @action(detail=True, methods=['post'])
    def add_movement(self, request, pk=None):
        session = self.get_object()
        if session.status != 'OPEN':
            return Response({'error': 'La caisse est fermée'}, status=400)

        serializer = CashMovementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(session=session)
        return Response(serializer.data, status=201)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        session = self.get_object()
        if session.status == 'CLOSED':
            return Response({'error': 'Caisse déjà fermée'}, status=400)

        closing = request.data.get('closing_balance')
        if closing is None:
            return Response({'error': 'closing_balance requis'}, status=400)

        total_in = session.movements.filter(type='IN').aggregate(t=Sum('amount'))['t'] or 0
        total_out = session.movements.filter(type='OUT').aggregate(t=Sum('amount'))['t'] or 0
        theoretical = session.opening_balance + total_in - total_out

        session.closing_balance = closing
        session.theoretical_balance = theoretical
        session.difference = float(closing) - float(theoretical)
        session.closed_at = timezone.now()
        session.status = 'CLOSED'
        session.save()

        return Response(CashSessionSerializer(session).data)


class ExpenseViewSet(viewsets.ModelViewSet):
    """
    Dépenses : OWNER, MANAGER, ACCOUNTANT
    """
    serializer_class = ExpenseSerializer

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewCash]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditCash]
        return [c() for c in classes]

    def get_queryset(self):
        qs = Expense.objects.filter(shop=self.request.user.shop)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user.shop)


class SupplierViewSet(viewsets.ModelViewSet):
    """
    Fournisseurs : OWNER, MANAGER uniquement
    """
    serializer_class = SupplierSerializer

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewSuppliers]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditSuppliers]
        return [c() for c in classes]

    def get_queryset(self):
        qs = Supplier.objects.filter(shop=self.request.user.shop)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user.shop)

    @action(detail=True, methods=['post'])
    def add_transaction(self, request, pk=None):
        supplier = self.get_object()
        serializer = SupplierTransactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(supplier=supplier)
        return Response(serializer.data, status=201)