from rest_framework import serializers
from .models import (
    CashSession, CashMovement, Expense, Supplier, SupplierTransaction
)


class CashMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashMovement
        fields = ['id', 'type', 'amount', 'category', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class CashSessionSerializer(serializers.ModelSerializer):
    movements = CashMovementSerializer(many=True, read_only=True)
    
    class Meta:
        model = CashSession
        fields = [
            'id', 'opening_balance', 'closing_balance',
            'theoretical_balance', 'difference',
            'opened_at', 'closed_at', 'status', 'movements',
        ]
        read_only_fields = ['id', 'opened_at', 'closed_at', 'status']


class ExpenseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = ['id', 'amount', 'category', 'description', 'expense_date', 'created_at']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        return Expense.objects.create(shop=self.context['request'].user.shop, **validated_data)


class SupplierTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierTransaction
        fields = ['id', 'type', 'amount', 'description', 'transaction_date', 'created_at']
        read_only_fields = ['id', 'created_at']


class SupplierSerializer(serializers.ModelSerializer):
    transactions = SupplierTransactionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'phone', 'address',
            'products_supplied', 'notes', 'created_at', 'transactions',
        ]
        read_only_fields = ['created_at']

    def create(self, validated_data):
        return Supplier.objects.create(shop=self.context['request'].user.shop, **validated_data)