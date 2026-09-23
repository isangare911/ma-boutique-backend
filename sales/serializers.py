from rest_framework import serializers
from .models import Sale, SaleItem


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = [
            'id', 'product', 'product_name', 'unit_price',
            'purchase_price', 'quantity', 'subtotal',
        ]
        read_only_fields = ['subtotal']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, required=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'total_amount', 'total_profit',
            'payment_method', 'status', 'created_at',
            'items',
        ]
        read_only_fields = ['created_at']

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        sale = Sale.objects.create(shop=self.context['request'].user.shop, **validated_data)
        
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)
        
        return sale