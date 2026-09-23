from django.contrib import admin
from .models import Sale, SaleItem


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ('id',)


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'total_amount', 'payment_method', 'status', 'created_at')
    list_filter = ('shop', 'status', 'payment_method')
    search_fields = ('id',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [SaleItemInline]