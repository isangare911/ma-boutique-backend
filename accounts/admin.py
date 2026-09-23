from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Shop


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