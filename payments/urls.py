from django.urls import path
from .views import create_order, verify_payment, wallet_pay, invoice_view
from . import views
urlpatterns = [
    path('create-order/', create_order),
    path('verify-payment/', verify_payment),
    path('wallet-pay/', wallet_pay),
    path("invoice/<int:order_id>/", invoice_view),

    path('invoice/<int:order_id>/', views.generate_invoice),
    
]
