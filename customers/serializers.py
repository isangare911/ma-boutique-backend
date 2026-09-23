from rest_framework import serializers
from .models import Customer, Credit, CreditPayment


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'address', 'created_at']
        read_only_fields = ['created_at']


class CreditPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditPayment
        fields = ['id', 'credit', 'amount', 'payment_method', 'payment_date', 'comment']
        read_only_fields = ['id']


class CreditSerializer(serializers.ModelSerializer):
    customer_detail = CustomerSerializer(source='customer', read_only=True)
    payments = CreditPaymentSerializer(many=True, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Credit
        fields = [
            'id', 'customer', 'customer_detail', 'total_amount',
            'paid_amount', 'remaining_amount', 'is_overdue',
            'created_at', 'due_date', 'notes', 'status',
            'payments',
        ]
        read_only_fields = ['created_at', 'status']

    def create(self, validated_data):
        return Credit.objects.create(shop=self.context['request'].user.shop, **validated_data)