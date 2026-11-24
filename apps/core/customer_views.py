"""
Customer presentation views for Homepage, Shopping Cart, Checkout, Order Confirmation,
Payment Result, and Customer Dashboard.
Designed to deliver a responsive customer ordering experience connecting Developer 2's templates
to backend models and services.
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.models import Address
from apps.menu.models import Category, FoodItem
from apps.menu.services import (
    get_active_categories,
    get_customer_menu_items,
    get_featured_offers,
)


@require_GET
def home_view(request: HttpRequest) -> HttpResponse:
    """Renders the responsive restaurant customer homepage with categories and daily offers."""
    categories = get_active_categories()
    items = get_customer_menu_items(featured_only=False)
    featured_offers = get_featured_offers()

    return render(
        request,
        "customer/home.html",
        {
            "categories": categories,
            "food_items": items,
            "featured_offers": featured_offers,
        },
    )


@require_GET
def cart_view(request: HttpRequest) -> HttpResponse:
    """Renders the shopping cart page with quantity controls, item removal, and order summary."""
    return render(request, "customer/cart.html")


@require_GET
def checkout_view(request: HttpRequest) -> HttpResponse:
    """Renders the checkout page with saved delivery address selection and order summaries."""
    addresses = []
    if request.user.is_authenticated:
        addresses = Address.objects.filter(user=request.user)

    return render(
        request,
        "customer/checkout.html",
        {
            "addresses": addresses,
        },
    )


@require_GET
def order_confirmation_view(request: HttpRequest) -> HttpResponse:
    """Renders the order confirmation page with status tracker timeline and itemized receipt."""
    ref = request.GET.get("ref", "")
    return render(
        request,
        "customer/order_confirmation.html",
        {
            "order_ref": ref,
        },
    )


@require_GET
def payment_result_view(request: HttpRequest) -> HttpResponse:
    """Renders the payment success or failure/retry page per PRD §4.13."""
    return render(request, "customer/payment_result.html")


@require_GET
def customer_dashboard_view(request: HttpRequest) -> HttpResponse:
    """Renders the customer dashboard with profile details, saved addresses, and order history."""
    addresses = []
    if request.user.is_authenticated:
        addresses = Address.objects.filter(user=request.user)

    return render(
        request,
        "customer/dashboard.html",
        {
            "addresses": addresses,
        },
    )
