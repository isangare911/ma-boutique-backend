from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F

from .models import Customer, Credit, CreditPayment
from .serializers import (
    CustomerSerializer, CreditSerializer, CreditPaymentSerializer
)
from accounts.permissions import (
    IsSameShop, CanViewCustomers, CanEditCustomers,
    CanViewCredits, CanEditCredits, CanCollectCreditPayment,
)


class CustomerViewSet(viewsets.ModelViewSet):
    """
    Clients : 
    - Lecture : OWNER, MANAGER, SELLER, ACCOUNTANT
    - Écriture : OWNER, MANAGER, SELLER
    """
    serializer_class = CustomerSerializer

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewCustomers]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditCustomers]
        return [c() for c in classes]

    def get_queryset(self):
        qs = Customer.objects.filter(shop=self.request.user.shop)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        serializer.save(shop=self.request.user.shop)


class CreditViewSet(viewsets.ModelViewSet):
    """
    Crédits :
    - Lecture : OWNER, MANAGER, SELLER, ACCOUNTANT
    - Écriture (création) : OWNER, MANAGER, SELLER
    - Encaissement : OWNER, MANAGER, SELLER, ACCOUNTANT
    """
    serializer_class = CreditSerializer
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            classes = [IsAuthenticated, IsSameShop, CanViewCredits]
        elif self.action == 'pay':
            classes = [IsAuthenticated, IsSameShop, CanCollectCreditPayment]
        else:
            classes = [IsAuthenticated, IsSameShop, CanEditCredits]
        return [c() for c in classes]

    def get_queryset(self):
        qs = Credit.objects.filter(shop=self.request.user.shop)

        status = self.request.query_params.get('status')
        if status:
            qs = qs.filter(status=status)

        overdue = self.request.query_params.get('overdue')
        if overdue == 'true':
            from django.utils import timezone
            qs = qs.filter(status='ACTIVE', due_date__lt=timezone.now())

        customer_id = self.request.query_params.get('customer')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)

        return qs.select_related('customer').prefetch_related('payments')

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """Enregistrer un remboursement"""
        credit = self.get_object()
        amount = request.data.get('amount')
        payment_method = request.data.get('payment_method', 'Espèces')

        if not amount or float(amount) <= 0:
            return Response({'error': 'Montant invalide'}, status=400)

        amount = float(amount)
        if amount > float(credit.remaining_amount):
            return Response(
                {'error': f'Le montant ne peut pas dépasser {credit.remaining_amount}'},
                status=400,
            )

        payment = CreditPayment.objects.create(
            credit=credit,
            amount=amount,
            payment_method=payment_method,
            comment=request.data.get('comment', ''),
        )

        credit.paid_amount = F('paid_amount') + amount
        credit.save()
        credit.refresh_from_db()

        return Response(CreditSerializer(credit).data)