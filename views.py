import braintree
import uuid

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.utils.timezone import now

from ..accounts import access

from .utils import check_customer, check_credit_card, get_subscription



# TODO: Add decorator to directly receive customer in each view

@login_required
@access(access.MANAGER)
def index(request):
    if not check_credit_card(request.user.access):
        return redirect('payment_add_credit_card')

    subscription = get_subscription(request.user.access)

    return render(request, 'payments/index.html', {
        'subscription': subscription
    })


@login_required
@access(access.MANAGER)
def add_credit_card(request):
    if not check_customer(request.user.access):
        messages.error(request, 'Could not synchronize customer')
        return redirect('payment_error')

    customer = request.user.access.customer

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

    months = ('%02d' % m for m in range(1, 13))
    upcomming_years = range(now().year, now().year + 10)

    customer.braintree_creditcard_token = cc_token
    customer.save()

    return render(request, 'payments/add_card.html',  {
        "tr_data": tr_data,
        "braintree_url": braintree_url,
        "months": months,
        "years": upcomming_years,

    })


@login_required
@access(access.MANAGER)
def confirm_credit_card(request):
    query_string = request.META['QUERY_STRING']
    result = braintree.TransparentRedirect.confirm(query_string)

    customer = request.user.access.customer

    if result.is_success:
        customer.braintree_creditcard_saved = now()
        customer.save()
        return redirect('payment_index')
    else:
        return render(request, 'payments/validation_error.html', {
            'result': result
        })


@login_required
@access(access.MANAGER)
def delete_credit_card(request):

    if not check_credit_card(request.user.access):
        return redirect('payment_add_credit_card')

    customer = request.user.access.customer

    result = braintree.CreditCard.delete(customer.braintree_creditcard_token)

    if result.is_success:
        customer.braintree_creditcard_saved = now()
        customer.save()
        return redirect('payment_index')
    else:
        return render(request, 'payments/validation_error.html', {
            'result': result
        })


@login_required
@access(access.MANAGER)
def subscribe_to_plan(request, plan_id):
    customer = request.user.access.customer

    if not check_credit_card(request.user.access):
        return redirect('payment_add_credit_card')

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


@login_required
def error(request):
    return render(request, 'payments/error.html')
