from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, TemplateView

from apps.core.permissions import RiderRequiredMixin
from apps.delivery.models import ACTIVE_STATUSES, Delivery
from apps.delivery.services import get_rider_deliveries


class RiderDashboardView(RiderRequiredMixin, TemplateView):
    template_name = "rider/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deliveries = get_rider_deliveries(self.request.user)
        active = deliveries.filter(status__in=ACTIVE_STATUSES)
        context["deliveries"] = deliveries
        context["active_deliveries"] = active
        context["completed_count"] = deliveries.filter(status="DELIVERED").count()
        return context


class RiderDeliveryDetailView(RiderRequiredMixin, DetailView):
    model = Delivery
    template_name = "rider/delivery_detail.html"
    context_object_name = "delivery"

    def get_queryset(self):
        return Delivery.objects.filter(rider__user=self.request.user).select_related(
            "rider", "rider__user", "customer"
        )


class CustomerTrackingView(LoginRequiredMixin, DetailView):
    model = Delivery
    template_name = "rider/tracking.html"
    context_object_name = "delivery"
    slug_field = "order_reference"
    slug_url_kwarg = "order_reference"

    def get_queryset(self):
        return Delivery.objects.visible_to(self.request.user).select_related(
            "rider", "rider__user", "customer"
        )
