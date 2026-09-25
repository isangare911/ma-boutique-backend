from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Shop
from .models import Payment
from django.utils.html import format_html
from .models import ShopUser

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'currency', 'subscription_plan', 'is_active', 'created_at')
    list_filter = ('subscription_plan', 'is_active', 'currency')
    search_fields = ('name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('phone', 'first_name', 'last_name', 'role', 'shop', 'is_active')
    list_filter = ('role', 'is_active', 'shop')
    search_fields = ('phone', 'first_name', 'last_name')
    ordering = ('phone',)
    
    fieldsets = (
        (None, {'fields': ('phone', 'password')}),
        ('Informations personnelles', {
            'fields': ('first_name', 'last_name', 'shop', 'role')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone', 'first_name', 'last_name', 'role', 'shop', 'password1', 'password2'),
        }),
    )

@admin.register(ShopUser)
class ShopUserAdmin(admin.ModelAdmin):
    list_display = ('user', 'shop', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('user__phone', 'shop__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'payment_code', 'shop', 'plan', 'amount',
        'method', 'status', 'transaction_id',
        'created_at', 'approve_actions',
    )
    list_filter = ('status', 'method', 'plan', 'created_at')
    search_fields = ('payment_code', 'transaction_id', 'shop__name', 'payer_phone')
    readonly_fields = (
        'id', 'payment_code', 'created_at', 'updated_at',
        'approved_at', 'proof_preview',
    )
    date_hierarchy = 'created_at'
    list_per_page = 50

    fieldsets = (
        ('Informations', {
            'fields': ('id', 'payment_code', 'shop', 'plan', 'amount', 'method', 'status')
        }),
        ('Paiement', {
            'fields': ('transaction_id', 'payer_phone', 'duration_days')
        }),
        ('Validation', {
            'fields': ('approved_by', 'approved_at', 'rejection_reason')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )

    def proof_preview(self, obj):
        """Affiche un aperçu de la preuve si elle existe."""
        if hasattr(obj, 'proof_image') and obj.proof_image:
            return format_html(
                '<a href="{0}" target="_blank">Voir la preuve</a>',
                obj.proof_image.url,
            )
        return '—'
    proof_preview.short_description = 'Preuve'

    def approve_actions(self, obj):
        """Bouton d'action rapide pour approuver."""
        if obj.status == 'PENDING_REVIEW':
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ À valider</span>'
            )
        elif obj.status == 'APPROVED':
            return format_html(
                '<span style="color: green;">✓ Approuvé</span>'
            )
        elif obj.status == 'REJECTED':
            return format_html(
                '<span style="color: red;">✗ Rejeté</span>'
            )
        return '—'
    approve_actions.short_description = 'Action'

    actions = ['approve_selected', 'reject_selected']

    def approve_selected(self, request, queryset):
        """Action pour approuver plusieurs paiements."""
        from .mobile_money_service import MobileMoneyService
        count = 0
        for payment in queryset.filter(status='PENDING_REVIEW'):
            try:
                MobileMoneyService.approve_payment(payment.id, request.user)
                count += 1
            except Exception as e:
                self.message_user(request, f'Erreur sur {payment.id}: {e}')
        self.message_user(request, f'{count} paiement(s) approuvé(s)')
    approve_selected.short_description = 'Approuver les paiements sélectionnés'

    def reject_selected(self, request, queryset):
        """Action pour rejeter plusieurs paiements."""
        from .mobile_money_service import MobileMoneyService
        count = 0
        for payment in queryset.filter(status='PENDING_REVIEW'):
            try:
                MobileMoneyService.reject_payment(
                    payment.id,
                    'Rejeté en masse par l\'admin',
                    request.user
                )
                count += 1
            except Exception as e:
                self.message_user(request, f'Erreur sur {payment.id}: {e}')
        self.message_user(request, f'{count} paiement(s) rejeté(s)')
    reject_selected.short_description = 'Rejeter les paiements sélectionnés'