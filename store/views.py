from rest_framework import generics, permissions
from .models import Product, ProductCategory, Order
from .serializers import ProductSerializer, ProductCategorySerializer, OrderSerializer

class ProductListView(generics.ListAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

class ProductCategoryListView(generics.ListAPIView):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.AllowAny]

class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show successful orders in My Orders
        return Order.objects.filter(
            customer=self.request.user,
            status__in=['PAID', 'SHIPPED', 'COMPLETED']
        ).order_by('-created_at')
