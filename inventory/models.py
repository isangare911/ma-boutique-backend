from django.db import models
import uuid


class Product(models.Model):
    """Produit du catalogue"""
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey(
        'accounts.Shop', on_delete=models.CASCADE, related_name='products'
    )
    name = models.CharField(max_length=200)
    reference = models.CharField(max_length=100, blank=True, null=True)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=100, blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quantity = models.IntegerField(default=0)
    alert_threshold = models.IntegerField(default=5)
    unit = models.CharField(max_length=50, blank=True, null=True)
    image_path = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['name']
        indexes = [
            models.Index(fields=['shop', 'name']),
            models.Index(fields=['shop', 'quantity']),
        ]

    def __str__(self):
        return f'{self.name} ({self.quantity} {self.unit or "u"})'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'PROD-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)

    @property
    def is_out_of_stock(self):
        return self.quantity == 0

    @property
    def is_low_stock(self):
        return 0 < self.quantity <= self.alert_threshold