from django.urls import path
from .views import (
    ProductListView,
    ProductCategoryListView,
    OrderListView,
    AdminSummaryView,
    AdminOrderListView,
    AdminOrderDetailView,
    AdminProductListCreateView,
    AdminProductDetailView,
)

urlpatterns = [
    path("products/", ProductListView.as_view(), name="product-list"),
    path("categories/", ProductCategoryListView.as_view(), name="category-list"),
    path("orders/", OrderListView.as_view(), name="order-list"),

    # staff/admin endpoints - REMOVE the "api/store/" prefix
    path("admin/summary/", AdminSummaryView.as_view(), name="admin-summary"),
    path("admin/orders/", AdminOrderListView.as_view(), name="admin-order-list"),
    path("admin/orders/<int:pk>/", AdminOrderDetailView.as_view(), name="admin-order-detail"),
    path("admin/products/", AdminProductListCreateView.as_view(), name="admin-product-list-create"),
    path("admin/products/<int:pk>/", AdminProductDetailView.as_view(), name="admin-product-detail"),
]