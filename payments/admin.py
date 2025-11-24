from django.contrib import admin
from .models import WalletTransaction, Invoice

admin.site.register(WalletTransaction)
admin.site.register(Invoice)
