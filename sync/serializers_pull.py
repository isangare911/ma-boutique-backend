# sync/serializers_pull.py
"""
Serializers pour le PULL (serveur → client).
Ils sont plus légers que les serializers d'écriture :
pas de validation complexe, juste de la sérialisation.
"""
from rest_framework import serializers

from inventory.models import Product
from customers.models import Customer, Credit, CreditPayment
from sales.models import Sale, SaleItem
from finance.models import (
    Expense, Supplier, SupplierTransaction, CashSession, CashMovement
)
from accounts.models import Shop


# ═══════════════════════════════════════════════════════════
# INVENTORY
# ═══════════════════════════════════════════════════════════
class ProductPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'reference', 'barcode', 'category',
            'purchase_price', 'selling_price', 'quantity',
            'alert_threshold', 'unit', 'image_path',
            'created_at', 'updated_at',
        ]


# ═══════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════
class CustomerPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'phone', 'address', 'created_at',
        ]


class CreditPaymentPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPayment
        fields = [
            'id', 'credit', 'amount', 'payment_method',
            'payment_date', 'comment',
        ]


class CreditPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Credit
        fields = [
            'id', 'customer', 'total_amount', 'paid_amount',
            'created_at', 'due_date', 'notes', 'status',
        ]


# ═══════════════════════════════════════════════════════════
# SALES
# ═══════════════════════════════════════════════════════════
class SaleItemPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = [
            'id', 'product', 'product_name', 'unit_price',
            'purchase_price', 'quantity', 'subtotal',
        ]


class SalePullSerializer(serializers.ModelSerializer):
    items = SaleItemPullSerializer(many=True, read_only=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'total_amount', 'total_profit',
            'payment_method', 'status', 'created_at', 'items',
        ]


# ═══════════════════════════════════════════════════════════
# FINANCE
# ═══════════════════════════════════════════════════════════
class ExpensePullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            'id', 'amount', 'category', 'description',
            'expense_date', 'created_at',
        ]


class SupplierPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'phone', 'address',
            'products_supplied', 'notes', 'created_at',
        ]


class SupplierTransactionPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierTransaction
        fields = [
            'id', 'supplier', 'type', 'amount', 'description',
            'transaction_date', 'created_at',
        ]


class CashMovementPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = CashMovement
        fields = [
            'id', 'type', 'amount', 'category',
            'description', 'created_at',
        ]


class CashSessionPullSerializer(serializers.ModelSerializer):
    movements = CashMovementPullSerializer(many=True, read_only=True)

    class Meta:
        model = CashSession
        fields = [
            'id', 'opening_balance', 'closing_balance',
            'theoretical_balance', 'difference',
            'opened_at', 'closed_at', 'status', 'movements',
        ]


# ═══════════════════════════════════════════════════════════
# SHOP SETTINGS
# ═══════════════════════════════════════════════════════════
class ShopPullSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = [
            'id', 'name', 'logo_path', 'currency',
            'address', 'phone', 'email', 'owner_name',
            'subscription_plan', 'subscription_status',
            'subscription_start', 'subscription_end',
            'is_active',
        ]