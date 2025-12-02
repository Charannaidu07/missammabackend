from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('phone', 'wallet_balance', 'is_customer', 'is_staff_member')}),
    )

admin.site.register(User, CustomUserAdmin)
