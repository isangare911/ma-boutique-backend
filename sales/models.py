from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


class Sale(models.Model):
    """Vente enregistrée"""
    STATUS_CHOICES = [
        ('COMPLETED', 'Complétée'),
        ('CANCELLED', 'Annulée'),
    ]

    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey(
        'accounts.Shop', on_delete=models.CASCADE, related_name='sales'
    )
    customer = models.ForeignKey(
        'customers.Customer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    total_profit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )
    payment_method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', '-created_at']),
            models.Index(fields=['shop', 'status']),
        ]

    def __str__(self):
        return f'{self.id} — {self.total_amount}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'SALE-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)


class SaleItem(models.Model):
    """Ligne d'une vente (produit + quantité + prix)"""
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_items',
    )
    product_name = models.CharField(max_length=200)  # Dénormalisé
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        validators=[MinValueValidator(Decimal('0'))],
    )
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],  # ⚡ > 0 obligatoire
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )

    class Meta:
        db_table = 'sale_items'

    def __str__(self):
        return f'{self.product_name} x{self.quantity}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'ITEM-{uuid.uuid4().hex[:12].upper()}'
        # ⚡ Toujours recalculer le subtotal (plus de bug si quantity change)
        if self.unit_price is not None and self.quantity is not None:
            self.subtotal = self.unit_price * self.quantity
        super().save(*args, **kwargs)