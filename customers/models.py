from django.db import models
from django.utils import timezone
import uuid


class Customer(models.Model):
    """Client de la boutique"""
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey(
        'accounts.Shop', on_delete=models.CASCADE, related_name='customers'
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, null=True)
    address = models.CharField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'customers'
        ordering = ['name']
        indexes = [models.Index(fields=['shop', 'name'])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'CLI-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)


class Credit(models.Model):
    """Crédit accordé à un client"""
    STATUS_CHOICES = [
        ('ACTIVE', 'En cours'),
        ('PAID', 'Payé'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    shop = models.ForeignKey(
        'accounts.Shop', on_delete=models.CASCADE, related_name='credits'
    )
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name='credits'
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')

    class Meta:
        db_table = 'credits'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['shop', 'status']),
            models.Index(fields=['shop', 'due_date']),
        ]

    def __str__(self):
        return f'{self.customer.name} — {self.total_amount}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'CRED-{uuid.uuid4().hex[:12].upper()}'
        # Mise à jour automatique du statut
        if self.paid_amount >= self.total_amount:
            self.status = 'PAID'
        super().save(*args, **kwargs)

    @property
    def remaining_amount(self):
        return self.total_amount - self.paid_amount

    @property
    def is_overdue(self):
        return self.status == 'ACTIVE' and timezone.now() > self.due_date

    @property
    def is_due_soon(self):
        if self.status != 'ACTIVE':
            return False
        delta = self.due_date - timezone.now()
        return 0 < delta.days <= 7


class CreditPayment(models.Model):
    """Remboursement d'un crédit"""
    id = models.CharField(max_length=50, primary_key=True, editable=False)
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_date = models.DateTimeField(default=timezone.now)
    comment = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'credit_payments'
        ordering = ['-payment_date']

    def __str__(self):
        return f'{self.credit.customer.name} — {self.amount}'

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = f'PAY-{uuid.uuid4().hex[:12].upper()}'
        super().save(*args, **kwargs)