"""
URL routes for the Customer Website, Menu Interface & Shopping Experience.
Owned by Developer 2.
"""
from django.urls import path

from . import customer_views

app_name = "customer"

urlpatterns = [
    path("", customer_views.home_view, name="home"),
    path("cart/", customer_views.cart_view, name="cart"),
    path("checkout/", customer_views.checkout_view, name="checkout"),
    path("orders/confirmation/", customer_views.order_confirmation_view, name="order-confirmation"),
    path("orders/payment-result/", customer_views.payment_result_view, name="payment-result"),
    path("dashboard/", customer_views.customer_dashboard_view, name="dashboard"),
]
