
import braintree
from braintree.exceptions.not_found_error import NotFoundError


def check_customer(access):
    user = access.user
    customer = access.customer

    if not customer.braintree_created:
        result = braintree.Customer.create({
            "id": str(customer.id),
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "company": customer.company,
            "email": user.email
        })

        if result.is_success:
            customer.braintree_created = now()
            customer.braintree_updated = now()
            customer.save()

    if customer.braintree_created and not customer.braintree_address_id:
        result = braintree.Address.create({
            "customer_id": str(customer.id),
            "first_name": customer.first_name,
            "last_name": customer.last_name,
            "company": customer.company,
            "street_address": customer.street,
            #"extended_address": "Suite 403",
            "locality": customer.city,
            "region": customer.state,
            "postal_code": customer.zip_code,
            "country_code_alpha2": customer.country.code
        })

        if result.is_success:
            customer.braintree_address_id = result.address.id
            customer.save()

    return customer.braintree_created and customer.braintree_address_id


def check_credit_card(access):
    customer = access.customer

    if customer.braintree_creditcard_saved:
        try:
            credit_card = braintree.CreditCard.find(
                customer.braintree_creditcard_token
            )

        except NotFoundError:
            customer.braintree_creditcard_saved = None
            customer.braintree_creditcard_token = None
            customer.save()

    return customer.braintree_creditcard_token and \
           customer.braintree_creditcard_saved


def get_subscription(access):
    customer = access.customer


    if customer.braintree_subscription:
        try:
            subscription = braintree.Subscription.find(
                customer.braintree_subscription
            )

            return subscription
        except NotFoundError:
            customer.braintree_subscription = None
            customer.save()

    return None

