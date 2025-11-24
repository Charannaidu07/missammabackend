from django.urls import path
from .views import ProductListView, ProductCategoryListView, OrderListView

urlpatterns = [
    path('products/', ProductListView.as_view()),
    path('categories/', ProductCategoryListView.as_view()),
    path('orders/', OrderListView.as_view()),
]
