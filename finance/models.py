from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid


# ═══════════════════════════════════════════════════════════
# CAISSE
# ═══════════════════════════════════════════════════════════
class CashSession(models.Model):
    """Session de caisse (ouverture → fermeture)"""
    STATUS_CHOICES = [
        ('OPEN', 'Ouverte'),
        ('CLOSED', 'Fermée'),
    ]

    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey('accounts.Shop', on_delete=models.CASCADE, related_name='cash_sessions')
    opening_balance = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
    )
    closing_balance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal('0'))],
    )
    theoretical_balance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    difference = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')

    class Meta:
        db_table = 'cash_sessions'
        ordering = ['-opened_at']

    def __str__(self):
        return f'{self.id} — {self.status}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'CASH-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)


class CashMovement(models.Model):
    """Mouvement de caisse (entrée ou sortie)"""
    TYPE_CHOICES = [
        ('IN', 'Entrée'),
        ('OUT', 'Sortie'),
    ]

    id = models.CharField(max_length=50, primary_key=True, editable=False)
    session = models.ForeignKey(CashSession, on_delete=models.CASCADE, related_name='movements')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],  # ⚡ > 0
    )
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'cash_movements'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.type} — {self.amount}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'MOV-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════
# DÉPENSES
# ═══════════════════════════════════════════════════════════
class Expense(models.Model):
    """Dépense du commerce"""
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey('accounts.Shop', on_delete=models.CASCADE, related_name='expenses')
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    category = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    expense_date = models.DateTimeField(default=timezone.now, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'expenses'
        ordering = ['-expense_date']
        indexes = [models.Index(fields=['shop', '-expense_date'])]

    def __str__(self):
        return f'{self.category} — {self.amount}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'EXP-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════
# FOURNISSEURS
# ═══════════════════════════════════════════════════════════
class Supplier(models.Model):
    """Fournisseur"""
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey('accounts.Shop', on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, null=True)
    address = models.CharField(max_length=500, blank=True, null=True)
    products_supplied = models.CharField(max_length=500, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'SUP-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)


class SupplierTransaction(models.Model):
    """Transaction avec un fournisseur (achat, paiement, dette)"""
    TYPE_CHOICES = [
        ('PURCHASE', 'Achat'),
        ('PAYMENT', 'Paiement'),
        ('DEBT', 'Dette'),
    ]

    id = models.CharField(max_length=50, primary_key=True, editable=False)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    description = models.TextField(blank=True, null=True)
    transaction_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'supplier_transactions'
        ordering = ['-transaction_date']

    def __str__(self):
        return f'{self.type} — {self.amount}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'STR-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)