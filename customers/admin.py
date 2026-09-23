from django.contrib import admin
from .models import Customer, Credit, CreditPayment


class CreditPaymentInline(admin.TabularInline):
    model = CreditPayment
    extra = 0
    readonly_fields = ('id',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'phone')
    list_filter = ('shop',)
    search_fields = ('name', 'phone')


@admin.register(Credit)
class CreditAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'total_amount', 'paid_amount', 'remaining_amount', 'status', 'due_date')
    list_filter = ('shop', 'status')
    search_fields = ('customer__name',)
    inlines = [CreditPaymentInline]