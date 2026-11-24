from django.contrib.auth import get_user_model

User = get_user_model()

ORDER_REFERENCE_FIELDS = ("reference", "order_reference", "order_number")
ORDER_OWNER_ID_FIELDS = ("customer_id", "user_id", "placed_by_id", "owner_id")
ORDER_OWNER_FIELDS = ("customer", "user", "placed_by", "owner")
ORDER_ADDRESS_FIELDS = ("delivery_address", "shipping_address", "address")


def get_order_model():
    try:
        from apps.orders.models import Order
    except (ImportError, AttributeError, LookupError):
        return None
    return Order


def get_order_by_reference(order_reference: str):
    model = get_order_model()
    if model is None or not order_reference:
        return None
    for field_name in ORDER_REFERENCE_FIELDS:
        if hasattr(model, field_name):
            return model.objects.filter(**{field_name: order_reference}).first()
    return None


def get_order_owner(order_reference: str):
    order = get_order_by_reference(order_reference)
    if order is None:
        return None
    for field_name in ORDER_OWNER_FIELDS:
        owner = getattr(order, field_name, None)
        if owner is not None:
            return owner
    for field_name in ORDER_OWNER_ID_FIELDS:
        owner_id = getattr(order, field_name, None)
        if owner_id:
            return User.objects.filter(pk=owner_id).first()
    return None


def get_order_owner_id(order_reference: str) -> int | None:
    owner = get_order_owner(order_reference)
    return owner.pk if owner is not None else None


def get_order_status(order_reference: str) -> str | None:
    order = get_order_by_reference(order_reference)
    return getattr(order, "status", None) if order is not None else None


def get_order_delivery_details(order_reference: str) -> dict:
    result = {
        "order_id": None,
        "customer": None,
        "destination_lat": None,
        "destination_lng": None,
        "destination_address": "",
    }
    order = get_order_by_reference(order_reference)
    if order is None:
        return result

    result["order_id"] = getattr(order, "id", None)
    result["customer"] = get_order_owner(order_reference)

    address = None
    for field_name in ORDER_ADDRESS_FIELDS:
        address = getattr(order, field_name, None)
        if address is not None:
            break

    result["destination_lat"] = getattr(address, "latitude", None) or getattr(
        order, "delivery_latitude", None
    )
    result["destination_lng"] = getattr(address, "longitude", None) or getattr(
        order, "delivery_longitude", None
    )
    if address is not None:
        result["destination_address"] = str(address)
    else:
        result["destination_address"] = getattr(order, "delivery_address_text", "") or ""
    return result
