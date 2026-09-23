from django.contrib import admin
from .models import SyncLog


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ('shop', 'operation_type', 'entity_type', 'entity_id', 'status', 'created_at')
    list_filter = ('status', 'entity_type', 'shop')
    search_fields = ('entity_id',)
    readonly_fields = ('created_at',)