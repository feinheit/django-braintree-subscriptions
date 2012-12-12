from braintree import WebhookNotification
import braintree
from pprint import pformat

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _

from ..accounts import access

from .utils import sync_customer
from .models import CreditCard, Plan, Subscription, Transaction, WebhookLog


# TODO: Add decorator to directly receive customer in each view
@access(access.MANAGER)
def index(request):
    customer = request.access.customer

    sync_customer(customer)

    if not customer.braintree.credit_cards.has_default():
        return redirect('payment_add_credit_card')

    subscriptions = customer.braintree.subscriptions.running()
    subscribed_plan_ids = subscriptions.values_list('plan__id')
    unsubscribed_plans = Plan.objects.exclude(id__in=subscribed_plan_ids)

    return render(request, 'payments/index.html', {
        'unsubscribed_plans': unsubscribed_plans,
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

    #cc_token = str(uuid.uuid1())

    tr_data = braintree.CreditCard.tr_data_for_create(
        {
            "credit_card": {
                "customer_id": str(customer.id),
                #"token": cc_token,
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


@access(access.MANAGER)
def subscribe(request, plan_id):
    customer = request.user.access.customer
    # Make sure plan exists
    plan = get_object_or_404(Plan, plan_id=plan_id)
    running_subscriptions = customer.braintree.subscriptions.running()

    if running_subscriptions.filter(plan__plan_id=plan_id).count():
        messages.info(request, _('You are already subscribed to this plan'))
        return redirect('payment_index')

    if not customer.braintree.credit_cards.has_default():
        messages.error(request, _('No default Credit Card defined'))
        return redirect('payment_index')

    subscription = Subscription()
    subscription.customer = customer.braintree
    subscription.plan = plan

    try:
        subscription.push()
        subscription.save()
        messages.success(request,
            _('You have been successfully subscribed to plan %(plan)s') % {
                'plan': plan_id
            }
        )
    except ValidationError as e:
        messages.error(request,
            _('You could not be subscribed because: %(message)s') % {
                'message': e.messages[0]
            }
        )

    return redirect('payment_index')


@access(access.MANAGER)
def unsubscribe(request, subscription_id):
    subscription = get_object_or_404(Subscription, subscription_id=subscription_id)

    result = subscription.cancel()

    if result.is_success:
        messages.warning(request,
            _('Your subscription to %(plan)s was canceled') % {
                'plan': subscription.plan_id
            }
        )
        return redirect('payment_index')
    else:
        error_codes = (error.code for error in result.errors.deep_errors)
        if '81905' in error_codes:  # Subscription already canceled
            subscription.status = Subscription.CANCELED
            subscription.save()
            return redirect('payment_index')

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
