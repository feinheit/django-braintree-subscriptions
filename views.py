from braintree import WebhookNotification
import braintree
import traceback
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

from models import BTCreditCard, BTPlan, BTSubscription, BTTransaction
from models import BTWebhookLog


# TODO: Add decorator to directly receive customer in each view
@access(access.MANAGER)
def index(request):
    customer = request.access.customer

    sync_customer(customer)

    if not customer.braintree.credit_cards.has_default():
        return redirect('payment_add_credit_card')

    subscriptions = customer.braintree.subscriptions.running()
    subscribed_plan_ids = subscriptions.values_list('plan__id')
    unsubscribed_plans = BTPlan.objects.exclude(id__in=subscribed_plan_ids)

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
        creditcard = BTCreditCard(
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
    card = get_object_or_404(BTCreditCard, token=token)
    card.delete()
    return redirect('payment_index')


@access(access.MANAGER)
def subscribe(request, plan_id):
    customer = request.user.access.customer
    plan = get_object_or_404(BTPlan, plan_id=plan_id)
    running_subscriptions = customer.braintree.subscriptions.running()

    if running_subscriptions.filter(plan__plan_id=plan_id).count():
        messages.info(request, _('You are already subscribed to this plan'))
        return redirect('payment_index')

    if not customer.braintree.credit_cards.has_default():
        messages.error(request, _('No default Credit Card defined'))
        return redirect('payment_index')

    subscription = BTSubscription()
    subscription.customer = customer.braintree
    subscription.plan = plan

    try:
        subscription.push()
        # Webhooks COULD have already saved this subscription
        try:
            subscription_id = subscription.subscription_id
            BTSubscription.objects.get(subscription_id=subscription_id)
        except BTSubscription.DoesNotExist:
            # Save otherwise
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
    subscription = get_object_or_404(BTSubscription,
        subscription_id=subscription_id)

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
            subscription.status = BTSubscription.CANCELED
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
    elif 'bt_signature' in request.POST and 'bt_payload' in request.POST:
        bt_signature = str(request.POST['bt_signature'])
        bt_payload = str(request.POST['bt_payload'])
        notification = WebhookNotification.parse(bt_signature, bt_payload)
        return handle_webhook_notficiation(notification)
    else:
        return HttpResponse("I don't understand you")


def handle_webhook_notficiation(notification):
    log = BTWebhookLog(kind=notification.kind)
    try:
        log.data = pformat(bt_to_dict(notification.subscription), indent=2)

        token = notification.subscription.payment_method_token
        card = BTCreditCard.objects.get(token=token)

        plan_id = notification.subscription.plan_id
        plan = BTPlan.objects.get(plan_id=plan_id)

        # Update subscription
        subscription, created = BTSubscription.objects.get_or_create(
            subscription_id=notification.subscription.id,
            customer=card.customer,
            plan=plan
        )

        subscription.import_data(notification.subscription)
        subscription.save()

        # Import transactions
        if notification.kind == "subscription_charged_successfully":
            for transaction in notification.subscription.transactions:
                trans, created = BTTransaction.objects.get_or_create(
                    transaction_id=transaction.id,
                    subscription=subscription,
                )

                trans.import_data(transaction)
                trans.save()
    except:
        log.exception = traceback.format_exc()
        raise
    finally:
        log.save()

    return HttpResponse('Ok, thanks')


@access(access.MANAGER)
def error(request):
    return render(request, 'payments/error.html')
