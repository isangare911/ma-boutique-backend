from rest_framework import serializers
from django.db import transaction
from django.db.models import F
from decimal import Decimal, InvalidOperation
from .models import Sale, SaleItem
from inventory.models import Product


class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = [
            'id', 'product', 'product_name', 'unit_price',
            'purchase_price', 'quantity', 'subtotal',
        ]
        read_only_fields = ['id', 'subtotal']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, required=True)

    class Meta:
        model = Sale
        fields = [
            'id', 'customer', 'total_amount', 'total_profit',
            'payment_method', 'status', 'created_at',
            'items',
        ]
        read_only_fields = [
            'id', 'created_at',
            'total_amount',  # ⚡ calculé côté serveur
            'total_profit',  # ⚡ calculé côté serveur
        ]

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError('Au moins un article est requis.')
        if len(items) > 100:
            raise serializers.ValidationError(
                'Maximum 100 articles par vente.'
            )
        return items

    def validate_customer(self, customer):
        request = self.context.get('request')
        if customer and request and customer.shop_id != request.user.shop_id:
            raise serializers.ValidationError(
                'Ce client n\'appartient pas à votre boutique.'
            )
        return customer

    def validate(self, data):
        request = self.context.get('request')
        if not request:
            return data

        shop_id = request.user.shop_id
        for item in data.get('items', []):
            product = item.get('product')
            if product and product.shop_id != shop_id:
                raise serializers.ValidationError(
                    f'Le produit {product.name} n\'appartient pas à votre boutique.'
                )
        return data

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop('items', [])

        # ═══════════════════════════════════════════════════════
        # 1. Calculer total_amount et total_profit (côté serveur)
        # ═══════════════════════════════════════════════════════
        total_amount = Decimal('0')
        total_profit = Decimal('0')

        for item_data in items_data:
            unit_price = item_data.get('unit_price') or Decimal('0')
            purchase_price = item_data.get('purchase_price') or Decimal('0')
            quantity = item_data.get('quantity') or 0

            subtotal = unit_price * quantity
            profit = (unit_price - purchase_price) * quantity

            total_amount += subtotal
            total_profit += profit

        # ═══════════════════════════════════════════════════════
        # 2. Créer la vente
        # ═══════════════════════════════════════════════════════
        sale = Sale.objects.create(
            shop=self.context['request'].user.shop,
            total_amount=total_amount,
            total_profit=total_profit,
            **validated_data,
        )

        # ═══════════════════════════════════════════════════════
        # 3. Créer les items + DÉCRÉMENTER le stock
        # ═══════════════════════════════════════════════════════
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)

            product = item_data.get('product')
            quantity = item_data.get('quantity', 0)

            if product and quantity > 0:
                # ⚡ Verrouiller le produit pour éviter les race conditions
                locked_product = Product.objects.select_for_update().get(
                    id=product.id
                )

                if locked_product.quantity < quantity:
                    raise serializers.ValidationError(
                        f'Stock insuffisant pour {locked_product.name} '
                        f'({locked_product.quantity} disponible, '
                        f'{quantity} demandé).'
                    )

                # Décrémenter atomiquement
                Product.objects.filter(id=product.id).update(
                    quantity=F('quantity') - quantity,
                )

        return sale