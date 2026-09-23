from django.contrib import admin
from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'category', 'quantity', 'selling_price', 'is_low_stock')
    list_filter = ('shop', 'category')
    search_fields = ('name', 'reference', 'barcode')
    readonly_fields = ('created_at', 'updated_at')