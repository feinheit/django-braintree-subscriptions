import braintree
import uuid

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.utils.timezone import now

from ..accounts import access

from .utils import sync_customer
from .models import CreditCard


# TODO: Add decorator to directly receive customer in each view
@access(access.MANAGER)
def index(request):
    customer = request.access.customer

    try:
        btcustomer = customer.braintree
        btcustomer.credit_cards.latest('id')
    except ObjectDoesNotExist:
        return redirect('payment_add_credit_card')


    #subscription = get_subscription(request.user.access)

    return render(request, 'payments/index.html', {
        #'subscription': subscription
    })


@access(access.MANAGER)
def add_credit_card(request):
    customer = request.access.customer

    try:
        sync_customer(request.access.customer)
    except ValidationError as e:
        messages.error(request, e)
        return redirect('payment_error')

    cc_token = str(uuid.uuid1())

    tr_data = braintree.CreditCard.tr_data_for_create(
        {
            "credit_card": {
                "customer_id": str(customer.id),
                "token": cc_token,
                "options": {
                    "make_default": True,
                    "verify_card": True,
                    "fail_on_duplicate_payment_method": True,
                }
            }
        },
        request.build_absolute_uri(reverse('payment_confirm_credit_card'))
    )

    braintree_url = braintree.TransparentRedirect.url()

    return render(request, 'payments/add_card.html',  {
        "tr_data": tr_data,
        "braintree_url": braintree_url,
    })


@access(access.MANAGER)
def confirm_credit_card(request):
    customer = request.access.customer

    try:
        sync_customer(request.access.customer)
    except ValidationError as e:
        messages.error(request, e)
        return redirect('payment_error')

    query_string = request.META['QUERY_STRING']
    result = braintree.TransparentRedirect.confirm(query_string)

    if result.is_success:
        creditcard = CreditCard(
            token=result.credit_card.token,
            customer=customer.braintree
        )
        creditcard.pull()
        creditcard.save()
        return redirect('payment_index')
    else:
        return render(request, 'payments/validation_error.html', {
            'result': result
        })


@access(access.MANAGER)
def delete_credit_card(request, token):
    card = get_object_or_404(CreditCard, token=token)
    card.delete()
    return redirect('payment_index')

"""

@login_required
@access(access.MANAGER)
def subscribe_to_plan(request, plan_id):
    customer = request.user.access.customer

    # if not check_credit_card(request.user.access):
    #     return redirect('payment_add_credit_card')

    result = braintree.Subscription.create({
        "payment_method_token": customer.braintree_creditcard_token,
        "plan_id": plan_id,
        "trial_period": False
    })

    if result.is_success:
        customer.braintree_subscription = result.subscription.id
        customer.save()
        return redirect('payment_index')
    else:
        return render(request, 'payments/validation_error.html', {
            'result': result
        })


@login_required
@access(access.MANAGER)
def unsubscribe(request):
    subscription = get_subscription(request.user.access)

    if not subscription:
        return redirect('payment_index')

    customer = request.user.access.customer

    result = braintree.Subscription.cancel(customer.braintree_subscription)

    if result.is_success:
        customer.braintree_subscription = None
        customer.save()
        return redirect('payment_index')
    else:
        return render(request, 'payments/validation_error.html', {
            'result': result
        })
"""


@access(access.MANAGER)
def error(request):
    return render(request, 'payments/error.html')
