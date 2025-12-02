from rest_framework import generics, permissions
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from django.utils import timezone
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
import datetime

from .models import Product, ProductCategory, Order
from .serializers import (
    ProductSerializer,
    ProductCategorySerializer,
    AdminOrderSerializer,
    OrderSerializer,
)


class ProductListView(generics.ListAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

class ProductCategoryListView(generics.ListAPIView):
    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategorySerializer
    permission_classes = [permissions.AllowAny]


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only show successful orders in "My Orders"
        return (
            Order.objects.filter(
                customer=self.request.user,
                status__in=["PAID", "SHIPPED", "COMPLETED"],
            )
            .order_by("-created_at")
        )


class AdminSummaryView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()

        # ---------- BASIC TOTALS ----------
        total_orders = Order.objects.count()

        total_revenue = (
            Order.objects.filter(status="PAID")
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or 0
        )

        status_counts = (
            Order.objects.values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        last_7 = today - datetime.timedelta(days=6)
        orders_by_day_qs = (
            Order.objects.filter(created_at__date__gte=last_7)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(
                count=Count("id"),
                revenue=Sum("total_amount"),
            )
            .order_by("day")
        )

        orders_by_day = [
            {
                "day": row["day"].strftime("%Y-%m-%d"),
                "count": row["count"],
                "revenue": float(row["revenue"] or 0),
            }
            for row in orders_by_day_qs
        ]

        def pct_change(current, previous):
            if not previous or previous == 0:
                return None
            return (float(current - previous) / float(previous)) * 100.0

        # last week vs previous week
        last_week_start = today - datetime.timedelta(days=6)
        last_week_end = today

        prev_week_end = last_week_start - datetime.timedelta(days=1)
        prev_week_start = prev_week_end - datetime.timedelta(days=6)

        orders_last_week = Order.objects.filter(
            created_at__date__range=[last_week_start, last_week_end]
        ).count()
        orders_prev_week = Order.objects.filter(
            created_at__date__range=[prev_week_start, prev_week_end]
        ).count()

        income_last_week = (
            Order.objects.filter(
                status="PAID",
                created_at__date__range=[last_week_start, last_week_end],
            )
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or 0
        )
        income_prev_week = (
            Order.objects.filter(
                status="PAID",
                created_at__date__range=[prev_week_start, prev_week_end],
            )
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or 0
        )

        orders_last_week_change_pct = pct_change(
            orders_last_week, orders_prev_week
        )
        income_last_week_change_pct = pct_change(
            income_last_week, income_prev_week
        )

        # last 30 days vs previous 30 days
        last_month_start = today - datetime.timedelta(days=29)
        last_month_end = today

        prev_month_end = last_month_start - datetime.timedelta(days=1)
        prev_month_start = prev_month_end - datetime.timedelta(days=29)

        orders_last_month = Order.objects.filter(
            created_at__date__range=[last_month_start, last_month_end]
        ).count()
        orders_prev_month = Order.objects.filter(
            created_at__date__range=[prev_month_start, prev_month_end]
        ).count()

        income_last_month = (
            Order.objects.filter(
                status="PAID",
                created_at__date__range=[last_month_start, last_month_end],
            )
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or 0
        )
        income_prev_month = (
            Order.objects.filter(
                status="PAID",
                created_at__date__range=[prev_month_start, prev_month_end],
            )
            .aggregate(total=Sum("total_amount"))
            .get("total")
            or 0
        )

        orders_last_month_change_pct = pct_change(
            orders_last_month, orders_prev_month
        )
        income_last_month_change_pct = pct_change(
            income_last_month, income_prev_month
        )

        return Response(
            {
                "total_orders": total_orders,
                "total_revenue": float(total_revenue),
                "status_counts": list(status_counts),
                "orders_by_day": orders_by_day,
                "orders_last_week": orders_last_week,
                "orders_prev_week": orders_prev_week,
                "orders_last_week_change_pct": orders_last_week_change_pct,
                "orders_last_month": orders_last_month,
                "orders_prev_month": orders_prev_month,
                "orders_last_month_change_pct": orders_last_month_change_pct,
                "income_last_week": float(income_last_week or 0),
                "income_prev_week": float(income_prev_week or 0),
                "income_last_week_change_pct": income_last_week_change_pct,
                "income_last_month": float(income_last_month or 0),
                "income_prev_month": float(income_prev_month or 0),
                "income_last_month_change_pct": income_last_month_change_pct,
            }
        )




class AdminOrderListView(generics.ListAPIView):
    serializer_class = AdminOrderSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = (
            Order.objects.select_related("customer")
            .prefetch_related("items__product")
            .order_by("-created_at")
        )
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs


class AdminOrderDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AdminOrderSerializer
    permission_classes = [IsAdminUser]
    queryset = Order.objects.all()


class AdminProductListCreateView(generics.ListCreateAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]
    queryset = Product.objects.all().order_by("-id")


class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]
    queryset = Product.objects.all()
