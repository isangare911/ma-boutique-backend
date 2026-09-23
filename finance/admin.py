from django.contrib import admin
from .models import CashSession, CashMovement, Expense, Supplier, SupplierTransaction


class CashMovementInline(admin.TabularInline):
    model = CashMovement
    extra = 0
    readonly_fields = ('id',)


@admin.register(CashSession)
class CashSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'opening_balance', 'theoretical_balance', 'difference', 'status', 'opened_at')
    list_filter = ('shop', 'status')
    inlines = [CashMovementInline]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('id', 'shop', 'category', 'amount', 'expense_date')
    list_filter = ('shop', 'category')


class SupplierTransactionInline(admin.TabularInline):
    model = SupplierTransaction
    extra = 0
    readonly_fields = ('id',)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'phone', 'products_supplied')
    list_filter = ('shop',)
    search_fields = ('name', 'phone')
    inlines = [SupplierTransactionInline]