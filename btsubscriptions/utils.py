
from .models import BTCustomer, BTAddress


def sync_customer(customer):
    """ Make sure the customer exists in the vault and is up to date"""
    try:
        bt_customer = customer.braintree
    except BTCustomer.DoesNotExist:
        bt_customer = BTCustomer()
        bt_customer.id = customer

    if not bt_customer.created or customer.modified > bt_customer.updated:
        bt_customer.first_name = customer.first_name
        bt_customer.last_name = customer.last_name
        bt_customer.company = customer.company

        bt_customer.push()
        bt_customer.save()

    try:
        bt_address = bt_customer.addresses.latest()
    except BTAddress.DoesNotExist:
        bt_address = BTAddress()
        bt_address.customer = bt_customer

    if not bt_address.created or customer.modified > bt_address.updated:
        bt_address.first_name = customer.first_name
        bt_address.last_name = customer.last_name
        bt_address.company = customer.company
        bt_address.street_address = customer.street
        bt_address.locality = customer.city
        bt_address.region = customer.state
        bt_address.postal_code = customer.zip_code
        bt_address.country_code_alpha2 = customer.country.code

        bt_address.push()
        bt_address.save()
