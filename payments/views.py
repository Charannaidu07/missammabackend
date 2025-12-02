import decimal
import razorpay
from django.conf import settings
from django.utils.crypto import get_random_string
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from store.models import Order, OrderItem, Product
from .models import WalletTransaction, Invoice
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order(request):
    """
    Create Razorpay order + local Order.
    - Validates cart & billing.
    - If anything fails → NO Order is created, returns 400.
    """
    user = request.user
    data = request.data

    cart_items = data.get('cart_items') or []
    billing_name = data.get('billing_name')
    billing_address = data.get('billing_address')
    billing_phone = data.get('billing_phone')

    # 1) Validate basic data
    if not cart_items:
        return Response(
            {"detail": "Cart is empty or cart_items not provided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not billing_name or not billing_address or not billing_phone:
        return Response(
            {"detail": "Billing name, address and phone are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        total_amount = decimal.Decimal('0.00')
        # cache products so we don't hit DB twice
        products_cache = []

        # 2) First pass: validate products, quantity, stock and compute total
        for item in cart_items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)

            if product_id is None:
                return Response(
                    {"detail": "product_id missing in one of cart items"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                return Response(
                    {"detail": f"Product with id {product_id} does not exist."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                qty = int(quantity)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "Quantity must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if qty <= 0:
                return Response(
                    {"detail": "Quantity must be positive."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if product.stock < qty:
                return Response(
                    {"detail": f"Not enough stock for product '{product.name}'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            line_total = product.price * qty
            total_amount += line_total
            products_cache.append((product, qty))

        # 3) Create Razorpay order (or fake one if keys not set, for dev)
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            # DEV MODE: no real Razorpay call, just simulate
            fake_razorpay_order_id = f"fake_{get_random_string(10)}"
            razorpay_order_id = fake_razorpay_order_id
        else:
            try:
                rz_order = client.order.create(
                    dict(
                        amount=int(total_amount * 100),  # paise
                        currency='INR',
                        receipt=f"order_rcptid_temp_{get_random_string(6)}",
                        payment_capture='1',
                    )
                )
                razorpay_order_id = rz_order['id']
            except Exception as e:
                # If Razorpay fails, we STOP here. No Order is created.
                import traceback
                print("Razorpay create order error:", e)
                traceback.print_exc()
                return Response(
                    {"detail": f"Razorpay error: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # 4) Now everything is okay → create local Order + OrderItems
        order = Order.objects.create(
            customer=user,
            billing_name=billing_name,
            billing_address=billing_address,
            billing_phone=billing_phone,
            total_amount=total_amount,
            status='PENDING',      # becomes PAID after verify
            razorpay_order_id=razorpay_order_id,
        )

        for product, qty in products_cache:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=qty,
                price=product.price,
            )
            # update stock
            product.stock -= qty
            product.save()

        # 5) Return data needed for Razorpay checkout on frontend
        return Response(
            {
                "order_id": order.id,
                "razorpay_order_id": order.razorpay_order_id,
                "amount": int(total_amount * 100),
                "currency": "INR",
                "razorpay_key": settings.RAZORPAY_KEY_ID or "rzp_test_Rj4ZkhrbwcjGuU",
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        import traceback
        print("Unexpected error in create_order:", e)
        traceback.print_exc()
        return Response(
            {"detail": f"Internal error in create_order: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    """
    Verify Razorpay payment signature, mark order as PAID,
    give wallet cashback, and generate invoice.
    """
    import decimal
    import razorpay

    data = request.data

    order_id = data.get('order_id')
    razorpay_order_id = data.get('razorpay_order_id')
    razorpay_payment_id = data.get('razorpay_payment_id')
    razorpay_signature = data.get('razorpay_signature')

    # Basic validation
    if not order_id:
        return Response(
            {"detail": "order_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
        return Response(
            {"detail": "Razorpay order_id, payment_id and signature are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # 1) Get order belonging to this user
        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2) Verify signature using Razorpay utility
        client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )

        params_dict = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        }

        try:
            client.utility.verify_payment_signature(params_dict)
        except razorpay.errors.SignatureVerificationError as e:
            # Invalid payment
            return Response(
                {"detail": f"Signature verification failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 3) Mark order as PAID
        order.status = "PAID"
        order.payment_id = razorpay_payment_id
        order.payment_signature = razorpay_signature
        order.save()

        # 4) Wallet cashback (use Decimal, not float)
        cashback = (order.total_amount * decimal.Decimal("0.05")).quantize(
            decimal.Decimal("0.01")
        )
        request.user.wallet_balance += cashback
        request.user.save()

        WalletTransaction.objects.create(
            user=request.user,
            amount=cashback,
            transaction_type="CREDIT",
            note=f"Cashback for order #{order.id}",
        )

        # 5) Create invoice
        invoice_no = f"MSM-{get_random_string(8).upper()}"
        Invoice.objects.create(order=order, invoice_number=invoice_no)

        return Response({"status": "success", "invoice_no": invoice_no}, status=200)

    except Exception as e:
        import traceback
        print("Error in verify_payment:", e)
        traceback.print_exc()

        return Response(
            {"detail": f"Internal error in verify_payment: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from store.models import Order, OrderItem
from .models import Invoice

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_invoice(request, order_id):
    """
    Returns HTML invoice the user can print.
    """
    try:
        order = get_object_or_404(Order, id=order_id, customer=request.user)

        try:
            invoice = Invoice.objects.get(order=order)
        except Invoice.DoesNotExist:
            return Response(
                {"detail": "Invoice not generated for this order."},
                status=400
            )

        items = OrderItem.objects.filter(order=order).select_related('product')
        
        # Calculate cashback for Razorpay orders
        cashback_amount = 0
        if order.razorpay_order_id and order.status == 'PAID':
            cashback_amount = (order.total_amount * decimal.Decimal("0.05")).quantize(
                decimal.Decimal("0.01")
            )

        return render(request, "invoice_template.html", {
            "order": order,
            "items": items,
            "invoice": invoice,
            "customer": request.user,
            "cashback_amount": cashback_amount,
        })

    except Exception as e:
        import traceback
        print("Invoice error:", e)
        traceback.print_exc()

        return Response(
            {"detail": "Invoice rendering failed: " + str(e)},
            status=500
        )












@api_view(['POST'])
@permission_classes([IsAuthenticated])
def wallet_pay(request):
    """
    Pay for cart fully using wallet.
    - If wallet balance is insufficient: NO order is created, returns 400.
    - If success: creates Order + OrderItems, deducts wallet, returns invoice_no.
    """
    user = request.user
    data = request.data

    cart_items = data.get('cart_items', [])
    billing_name = data.get('billing_name')
    billing_address = data.get('billing_address')
    billing_phone = data.get('billing_phone')

    # Basic validation
    if not cart_items:
        return Response(
            {"detail": "Cart is empty or cart_items not provided."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not billing_name or not billing_address or not billing_phone:
        return Response(
            {"detail": "Billing name, address and phone are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        total_amount = decimal.Decimal('0.00')

        # First pass: compute total and validate products + stock
        for item in cart_items:
            product_id = item.get('product_id')
            quantity = item.get('quantity', 1)

            if product_id is None:
                raise ValueError("product_id missing in one of cart items")

            product = Product.objects.get(id=product_id)
            qty = int(quantity)
            if qty <= 0:
                raise ValueError("Quantity must be positive")

            if product.stock < qty:
                raise ValueError(f"Not enough stock for product '{product.name}'")

            line_total = product.price * qty
            total_amount += line_total

        # Check wallet BEFORE creating order
        if user.wallet_balance < total_amount:
            return Response(
                {
                    "detail": "Insufficient wallet balance.",
                    "required": str(total_amount),
                    "available": str(user.wallet_balance),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Now we are sure we can pay → create order + items
        order = Order.objects.create(
            customer=user,
            billing_name=billing_name,
            billing_address=billing_address,
            billing_phone=billing_phone,
            total_amount=total_amount,
            status='PAID',
        )

        for item in cart_items:
            product_id = item.get('product_id')
            quantity = int(item.get('quantity', 1))
            product = Product.objects.get(id=product_id)

            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price,
            )

            product.stock -= quantity
            product.save()

        # Deduct wallet
        user.wallet_balance -= total_amount
        user.save()

        WalletTransaction.objects.create(
            user=user,
            amount=total_amount,
            transaction_type='DEBIT',
            note=f"Wallet payment for order #{order.id}"
        )

        # Invoice
        invoice_no = f"MSM-{get_random_string(8).upper()}"
        Invoice.objects.create(order=order, invoice_number=invoice_no)

        return Response(
            {"status": "success", "invoice_no": invoice_no, "order_id": order.id},
            status=status.HTTP_200_OK,
        )

    except Product.DoesNotExist:
        return Response(
            {"detail": "One of the products in the cart does not exist."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        import traceback
        print("Error in wallet_pay:", e)
        traceback.print_exc()
        return Response(
            {"detail": f"Internal error in wallet_pay: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from store.models import Order, OrderItem
from .models import Invoice

def invoice_view(request, order_id):
    """
    Simple invoice view: show invoice by order id only.
    (Good enough for project/college use)
    """
    order = get_object_or_404(Order, id=order_id)

    try:
        invoice = Invoice.objects.get(order=order)
    except Invoice.DoesNotExist:
        return HttpResponse("Invoice not generated yet.", status=400)

    items = OrderItem.objects.filter(order=order)

    return render(request, "invoice_template.html", {
        "order": order,
        "items": items,
        "invoice": invoice,
        "customer": order.customer,
    })
