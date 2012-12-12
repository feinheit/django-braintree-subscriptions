from braintree import WebhookNotification
import braintree
import uuid
from pprint import pformat

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from ..accounts import access

from .utils import sync_customer
from .models import CreditCard, Plan, Subscription, Transaction, WebhookLog


# TODO: Add decorator to directly receive customer in each view
@access(access.MANAGER)
def index(request):
    customer = request.access.customer

    try:
        btcustomer = customer.braintree
        btcustomer.credit_cards.latest('id')
    except ObjectDoesNotExist:
        return redirect('payment_add_credit_card')

    subscriptions = Subscription.objects.for_customer(customer)
    subscribed_plan_ids = [s.plan_id for s in subscriptions]
    unsubscribed_plans = Plan.objects.exclude(plan_id__in=subscribed_plan_ids)

    #subscription = get_subscription(request.user.access)
    return render(request, 'payments/index.html', {
        'plans': unsubscribed_plans,
        'subscriptions': subscriptions
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


def is_subscribed_to_plan(customer, plan_id):
    subscriptions = Subscription.objects.for_customer(customer)
    return subscriptions.filter(plan_id=plan_id).count()


@access(access.MANAGER)
def subscribe(request, plan_id):
    customer = request.user.access.customer
    # Make sure plan exists
    get_object_or_404(Plan, plan_id=plan_id)

    if is_subscribed_to_plan(customer, plan_id):
        messages.info(request, 'You are already subscribed to this plan')
        return redirect('payment_index')

    # TODO: this is stupid and should be removed
    card = customer.braintree.credit_cards.latest('id')

    subscription = Subscription()
    subscription.payment_method_token = card.token
    subscription.plan_id = plan_id

    try:
        subscription.push()
        subscription.save()
        messages.success(request,
            'You have been successfully subscribed to plan %s' % plan_id)
    except ValidationError as e:
        messages.error(request,
            'You could not be subscribed because: %s' % e.messages[0])

    return redirect('payment_index')


@access(access.MANAGER)
def unsubscribe(request, subscription_id):
    subscription = get_object_or_404(Subscription, subscription_id=subscription_id)

    result = subscription.cancel()

    if result.is_success:
        return redirect('payment_index')
    else:
        return render(request, 'payments/validation_error.html', {
            'result': result
        })


def bt_to_dict(resource):
    data = resource.__dict__
    for k in data.keys():
        if k.startswith('_'):
            del data[k]
    return data


@csrf_exempt
def webhook(request):

    if 'bt_challenge' in request.GET:
        challenge = request.GET['bt_challenge']
        return HttpResponse(WebhookNotification.verify(challenge))
    if 'bt_signature' in request.POST and 'bt_payload' in request.POST:
        bt_signature = str(request.POST['bt_signature'])
        bt_payload = str(request.POST['bt_payload'])

        notification = WebhookNotification.parse(bt_signature, bt_payload)

        log = WebhookLog(kind=notification.kind)

        if hasattr(notification, 'subscription'):
            subscription = notification.subscription

            log.data = pformat(bt_to_dict(subscription), indent=2)

            # Update subscription
            dbsub, created = Subscription.objects.get_or_create(
                subscription_id=subscription.id
            )

            dbsub.import_data(subscription)
            dbsub.save()

            if notification.kind == "subscription_charged_successfully":
                # Import transactions
                for transaction in subscription.transactions:
                    dbtrans, created = Transaction.objects.get_or_create(
                        transaction_id=transaction.id
                    )

                    dbtrans.import_data(transaction)
                    dbtrans.save()

        log.save()

        return HttpResponse('Ok, thanks')
    else:
        return HttpResponse("I don't understand you")


@access(access.MANAGER)
def error(request):
    return render(request, 'payments/error.html')
