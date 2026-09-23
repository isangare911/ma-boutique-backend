from django.db import models


class SyncLog(models.Model):
    """Log de synchronisation pour l'audit"""
    STATUS_CHOICES = [
        ('SUCCESS', 'Succès'),
        ('FAILED', 'Échec'),
    ]
    
    shop = models.ForeignKey('accounts.Shop', on_delete=models.CASCADE, related_name='sync_logs')
    operation_type = models.CharField(max_length=20)
    entity_type = models.CharField(max_length=50)
    entity_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sync_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.entity_type}/{self.entity_id} — {self.status}'