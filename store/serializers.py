from rest_framework import serializers
from rest_framework import serializers
from .models import ProductCategory, Product, Order, OrderItem
from django.conf import settings
import re

class ProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductCategory
        fields = '__all__'

class ProductSerializer(serializers.ModelSerializer):
    category = ProductCategorySerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    clean_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'price', 'stock', 
                 'image', 'image_url', 'clean_image', 'is_active', 'category']

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request is not None:
                return request.build_absolute_uri(obj.image.url)
            else:
                return f"{settings.BASE_URL}{obj.image.url}" if hasattr(settings, 'BASE_URL') else obj.image.url
        return None

    def get_clean_image(self, obj):
        """Provide cleaned image URL to fix corrupted filenames"""
        if not obj.image:
            return None
            
        # Clean the corrupted filenames
        original_url = obj.image.name if obj.image else ''
        
        # Fix the corruption patterns
        cleaned = original_url
        if 'nBets4pg' in cleaned:
            cleaned = cleaned.replace('nBets4pg', 'WhatsApp')
            cleaned = cleaned.replace('2015-11-30', '2025-11-20')
            cleaned = cleaned.replace('uL', 'at')
            cleaned = cleaned.replace('c0712a1d', 'cd712a1d')
            cleaned = re.sub(r'_([a-zA-Z0-9]{6,7})\.', '_', cleaned)
        
        # Return the cleaned URL
        request = self.context.get('request')
        if request is not None:
            return request.build_absolute_uri(cleaned)
        else:
            return f"{settings.BASE_URL}/media/{cleaned}" if hasattr(settings, 'BASE_URL') else f"/media/{cleaned}"
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "quantity", "price"]

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = '__all__'

class AdminOrderSerializer(serializers.ModelSerializer):
    customer_username = serializers.CharField(source="customer.username", read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer",
            "customer_username",
            "status",
            "delivery_status",
            "total_amount",
            "created_at",
            "billing_name",
            "billing_address",
            "billing_phone",
            "items",
        ]