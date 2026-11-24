"""
Comprehensive integration and unit test suite for Developer 2:
Customer Website, Menu Interface, Shopping Experience, Cart, Checkout, Dashboard & Order Confirmation.
"""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import Address, CustomerProfile, UserRole
from apps.core.models import RestaurantSettings
from apps.menu.models import Category, FoodItem

User = get_user_model()


class CustomerFrontendWorkflowTests(TestCase):
    """Verifies that all customer templates, routes, and interactions render correctly."""

    def setUp(self):
        self.client = Client()

        # Ensure restaurant settings singleton
        self.settings_obj = RestaurantSettings.get_solo()
        self.settings_obj.restaurant_name = "Cho Restaurant"
        self.settings_obj.currency = "GHS"
        self.settings_obj.currency_symbol = "GH₵"
        self.settings_obj.operating_country = "Ghana"
        self.settings_obj.save()

        # Seed categories
        self.cat_local = Category.objects.create(
            name="Local Ghanaian Dishes",
            slug="local-dishes",
            description="Authentic dishes fresh daily.",
            sort_order=1,
            is_active=True,
        )
        self.cat_drinks = Category.objects.create(
            name="Chilled Refreshments",
            slug="drinks",
            description="Natural juices and local drinks.",
            sort_order=2,
            is_active=True,
        )

        # Seed food items
        self.item_jollof = FoodItem.objects.create(
            category=self.cat_local,
            name="Assorted Jollof Rice with Chicken",
            slug="assorted-jollof-rice-with-chicken",
            description="Smoky Ghanaian party jollof with grilled chicken and kelewele.",
            price=Decimal("85.00"),
            is_available=True,
            is_featured=True,
            prep_time_minutes=25,
        )
        self.item_sobolo = FoodItem.objects.create(
            category=self.cat_drinks,
            name="Chilled Sobolo Hibiscus Drink",
            slug="chilled-sobolo-hibiscus-drink",
            description="Spiced with organic ginger, pineapple and cloves.",
            price=Decimal("20.00"),
            is_available=True,
            is_featured=False,
            prep_time_minutes=5,
        )
        self.item_soldout = FoodItem.objects.create(
            category=self.cat_local,
            name="Volta River Prawns",
            slug="volta-river-prawns",
            description="Grilled spicy prawns.",
            price=Decimal("150.00"),
            is_available=False,
            is_featured=False,
            prep_time_minutes=30,
        )

        # Seed a test customer user (signal automatically creates CustomerProfile)
        self.customer = User.objects.create_user(
            username="test_customer",
            email="customer@example.com",
            password="StrongPassword123!",
            first_name="Akua",
            last_name="Asante",
            phone="+233240001111",
            role=UserRole.CUSTOMER,
        )
        self.address = Address.objects.create(
            user=self.customer,
            label="Home",
            line1="14 Independence Avenue",
            line2="Ridge",
            city="Accra",
            state="Greater Accra",
            country="Ghana",
            is_default=True,
        )

    def test_homepage_renders_successfully_with_dishes_and_branding(self):
        """Visiting '/' renders customer/home.html with brand, categories and featured offers."""
        response = self.client.get(reverse("customer:home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/home.html")
        self.assertTemplateUsed(response, "customer/base.html")

        content = response.content.decode("utf-8")
        self.assertIn("Cho Restaurant", content)
        self.assertIn("Local Ghanaian Dishes", content)
        self.assertIn("Assorted Jollof Rice with Chicken", content)
        self.assertIn("GH₵", content)
        self.assertIn("AKWAABA10", content)

    def test_menu_list_renders_with_filters_and_search(self):
        """Visiting '/menu/' renders customer/menu_list.html with category tabs and availability."""
        response = self.client.get(reverse("menu:menu-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/menu_list.html")

        content = response.content.decode("utf-8")
        self.assertIn("Assorted Jollof Rice with Chicken", content)
        self.assertIn("Chilled Sobolo Hibiscus Drink", content)
        # Should not display unavailable item on public customer menu
        self.assertNotIn("Volta River Prawns", content)

        # Test search query
        search_res = self.client.get(reverse("menu:menu-list") + "?search=Jollof")
        self.assertEqual(search_res.status_code, 200)
        search_content = search_res.content.decode("utf-8")
        self.assertIn("Assorted Jollof", search_content)

        # Test featured filter
        feat_res = self.client.get(reverse("menu:menu-list") + "?featured=true")
        self.assertEqual(feat_res.status_code, 200)
        feat_content = feat_res.content.decode("utf-8")
        self.assertIn("Special Meals &amp; Daily Offers", feat_content)

    def test_category_detail_renders_filtered_dishes(self):
        """Visiting '/menu/categories/<slug>/' renders customer/category_detail.html."""
        response = self.client.get(reverse("menu:category-detail", kwargs={"slug": self.cat_drinks.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/category_detail.html")
        content = response.content.decode("utf-8")
        self.assertIn("Chilled Refreshments", content)
        self.assertIn("Chilled Sobolo Hibiscus Drink", content)

    def test_food_detail_renders_full_dish_information(self):
        """Visiting '/menu/items/<slug>/' renders customer/food_detail.html."""
        response = self.client.get(reverse("menu:food-detail", kwargs={"slug": self.item_jollof.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/food_detail.html")
        content = response.content.decode("utf-8")
        self.assertIn("Assorted Jollof Rice with Chicken", content)
        self.assertIn("85.00", content)
        self.assertIn("25 mins", content)
        self.assertIn("Special Instructions for Kitchen", content)

    def test_cart_page_renders_cleanly(self):
        """Visiting '/cart/' renders customer/cart.html with promo and order summary."""
        response = self.client.get(reverse("customer:cart"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/cart.html")
        content = response.content.decode("utf-8")
        self.assertIn("Shopping Cart", content)
        self.assertIn("Order Summary", content)
        self.assertIn("AKWAABA10", content)

    def test_checkout_page_renders_with_address_and_payment_choices(self):
        """Visiting '/checkout/' renders customer/checkout.html with address selection and payment options."""
        # Authenticated customer
        self.client.login(username="test_customer", password="StrongPassword123!")
        response = self.client.get(reverse("customer:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/checkout.html")
        content = response.content.decode("utf-8")
        self.assertIn("14 Independence Avenue", content)
        self.assertIn("Paystack Online", content)
        self.assertIn("Cash on Delivery", content)

    def test_order_confirmation_page_renders_with_tracker(self):
        """Visiting '/orders/confirmation/' renders customer/order_confirmation.html with live status timeline."""
        response = self.client.get(reverse("customer:order-confirmation") + "?ref=ORD-20261124-TEST01")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/order_confirmation.html")
        content = response.content.decode("utf-8")
        self.assertIn("ORD-20261124-TEST01", content)
        self.assertIn("Live Order Progress", content)

    def test_payment_result_page_handles_success_and_failure(self):
        """Visiting '/orders/payment-result/' renders customer/payment_result.html."""
        # Success
        res_ok = self.client.get(reverse("customer:payment-result") + "?status=success&ref=T12345")
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn("Payment Successful", res_ok.content.decode("utf-8"))

        # Failure per PRD §4.13
        res_fail = self.client.get(reverse("customer:payment-result") + "?status=failed")
        self.assertEqual(res_fail.status_code, 200)
        self.assertIn("Payment Could Not Be Completed", res_fail.content.decode("utf-8"))
        self.assertIn("Switch to Cash on Delivery", res_fail.content.decode("utf-8"))

    def test_customer_dashboard_renders_for_customer(self):
        """Visiting '/dashboard/' renders customer/dashboard.html."""
        self.client.login(username="test_customer", password="StrongPassword123!")
        response = self.client.get(reverse("customer:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "customer/dashboard.html")
        content = response.content.decode("utf-8")
        self.assertIn("Akua Asante", content)
        self.assertIn("Order History", content)

    def test_accounts_views_use_customer_templates(self):
        """Accounts login, register, profile, and addresses render Developer 2's templates."""
        # Login
        login_res = self.client.get(reverse("accounts:login"))
        self.assertEqual(login_res.status_code, 200)
        self.assertTemplateUsed(login_res, "customer/login.html")

        # Register
        reg_res = self.client.get(reverse("accounts:register"))
        self.assertEqual(reg_res.status_code, 200)
        self.assertTemplateUsed(reg_res, "customer/register.html")

        # Profile (logged in)
        self.client.login(username="test_customer", password="StrongPassword123!")
        prof_res = self.client.get(reverse("accounts:profile"))
        self.assertEqual(prof_res.status_code, 200)
        self.assertTemplateUsed(prof_res, "customer/profile.html")

        # Addresses
        addr_res = self.client.get(reverse("accounts:addresses"))
        self.assertEqual(addr_res.status_code, 200)
        self.assertTemplateUsed(addr_res, "customer/addresses.html")
