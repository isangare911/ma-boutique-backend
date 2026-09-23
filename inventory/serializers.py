from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'reference', 'barcode', 'category',
            'purchase_price', 'selling_price', 'quantity',
            'alert_threshold', 'unit', 'image_path',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']