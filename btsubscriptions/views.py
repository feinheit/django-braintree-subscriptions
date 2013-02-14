from braintree import WebhookNotification
import braintree
import traceback
from pprint import pformat

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import formats
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from .utils import sync_customer

from models import BTCreditCard, BTPlan, BTAddOn, BTDiscount
from models import BTSubscription, BTSubscribedAddOn, BTSubscribedDiscount
from models import BTTransaction, BTWebhookLog


def index(request):
    customer = request.access.customer

    try:
        sync_customer(request.access.customer)
    except ValidationError as e:
        messages.error(request, e)
        return redirect('payment_error')

    subscriptions = customer.braintree.subscriptions.running().select_related()

    # take care if customer has multiple subscriptions
    if subscriptions.count() > 1:
        return redirect('payment_multiple_subscriptions')

    card = customer.braintree.credit_cards.get_default()

    plans = BTPlan.objects.all()

    active_sub = subscriptions[0] if subscriptions else None

    subscribed_plan_ids = subscriptions.values_list('plan__plan_id', flat=True)

    add_ons = BTAddOn.objects.all()
    if active_sub:
        for add_on in add_ons:
            try:
                add_on.subscription = BTSubscribedAddOn.objects.get(
                    subscription=active_sub,
                    add_on=add_on
                )
            except BTSubscribedAddOn.DoesNotExist:
                pass

    transactions = BTTransaction.objects.for_customer(customer.braintree)

    return render(request, 'payments/index.html', {
        'card': card,
        'plans': plans,
        'subscriptions': subscriptions,
        'active_subscription': active_sub,
        'subscribed_plan_ids': subscribed_plan_ids,
        'add_ons': add_ons,
        'transactions': transactions
    })


def add_credit_card(request):
    customer = request.access.customer

    # optionally set plan to subscribe after the credit card has been confirmed
    if 'subscribe' in request.GET:
        request.session['subscribe_directly'] = request.GET['subscribe']

    #cc_token = str(uuid.uuid1())

    tr_data = braintree.CreditCard.tr_data_for_create(
        {
            "credit_card": {
                "customer_id": str(customer.id),
                #"token": cc_token,
                "options": {
                    "make_default": True,
                    "verify_card": True,
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
        # unset default credit card
        customer.braintree.credit_cards.update(default=False)

        creditcard = BTCreditCard(
            token=result.credit_card.token,
            customer=customer.braintree
        )
        creditcard.pull()
        creditcard.save()

        # update subscriptions to use new card
        for subscription in customer.braintree.subscriptions.running():
            subscription.push()
            subscription.save()

        if 'subscribe_directly' in request.session:
            plan_id = request.session['subscribe_directly']
            del request.session['subscribe_directly']
            return redirect('payment_subscribe', plan_id=plan_id)
        else:
            return redirect('payment_index')
    else:
        return render(request, 'payments/validation_error.html', {
            'result': result
        })


def subscribe(request, plan_id):
    customer = request.access.customer
    plan = get_object_or_404(BTPlan, plan_id=plan_id)

    if not customer.braintree.credit_cards.has_default():
        messages.error(request, _('No default Credit Card defined'))
        return redirect('payment_index')

    if customer.braintree.subscriptions.running().count() != 0:
        messages.error(request, _('You are already signed to a plan'))
        return redirect('payment_index')

    subscription = BTSubscription()
    subscription.customer = customer.braintree
    subscription.plan = plan

    try:
        subscription.clean()
        result = subscription.push()
        subscription.import_data(result.subscription)
        # Webhooks COULD have already saved this subscription
        if customer.braintree.subscriptions.running().count() == 0:
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


def unsubscribe(request, subscription_id):
    subscription = get_object_or_404(BTSubscription,
        subscription_id=subscription_id)

    result = subscription.cancel()

    if result.is_success:
        messages.warning(request,
            _('Your subscription to %(plan)s was canceled') % {
                'plan': subscription.plan
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


def change_to_plan(request, plan_id):
    customer = request.access.customer
    plan = get_object_or_404(BTPlan, plan_id=plan_id)

    running_subscriptions = customer.braintree.subscriptions.running()

    if running_subscriptions.count() > 1:
        return redirect('payment_multiple_subscriptions')
    if running_subscriptions.count() == 0:
        messages.error(request, _('You have no active subscription'))
        return redirect('payment_index')
    else:
        subscription = running_subscriptions[0]

    subscription.plan = plan
    subscription.price = plan.price
    subscription.number_of_billing_cycles = None

    try:
        result = subscription.push()
        subscription.import_data(result.subscription)
        subscription.save()
    except ValidationError:
        # Check if subscription is already canceled
        if '81901' in [e.code for e in result.errors.deep_errors]:
            subscription.status = BTSubscription.CANCELED
            subscription.save()
            messages.warning(request, _('Your subscription is canceled. '
                'Please subscribe again for a plan'))
        else:
            messages.error(request, result.message)

    return redirect('payment_index')


def multiple_subscriptions(request):
    customer = request.access.customer
    return render(request, 'payments/multiple_subscriptions.html', {
        'subscriptions': customer.braintree.subscriptions.running()
    })


def downgrade_to_free_plan(request):
    subscriptions = request.access.customer.braintree.subscriptions.running()

    if subscriptions.count() == 0:
        messages.error(request, _('No active subscription found!'))
        return redirect('payment_index')

    subscription = subscriptions[0]

    if subscription.current_billing_cycle is None:
        messages.error(request, _('Current billing cycle unknown'))
        return redirect('payment_index')

    # Set current billing cylce as the last one
    subscription.number_of_billing_cycles = subscription.current_billing_cycle
    result = subscription.push()

    if result.is_success:
        subscription.import_data(result.subscription)
        subscription.save()
        messages.info(request,
            _('Your subscription will end on the next billing date')
        )
    else:
        messages.error(request, result.message)

    return redirect('payment_index')


def enable_addon(request, sub_id, addon_id):
    subscription = get_object_or_404(BTSubscription, subscription_id=sub_id)
    add_on = get_object_or_404(BTAddOn, addon_id=addon_id)

    result = braintree.Subscription.update(sub_id, {
        'add_ons': {'add': [{'inherited_from_id': addon_id}]}
    })

    save_addon = True

    if result.is_success:
        subscription.import_data(result.subscription)
        subscription.save()
    elif '91911' in (error.code for error in result.errors.deep_errors):
        # Add-on is already active! Just continue and save add-on
        # TODO: We should check the quantity here
        pass
    else:
        save_addon = False
        messages.error(request, result.message)

    if save_addon:
        sub_add_on = BTSubscribedAddOn(subscription=subscription, add_on=add_on)
        sub_add_on.save()
        messages.success(request, u'Add-On %s successfully enabled' % addon_id)

    return redirect('payment_index')


def disable_addon(request, sub_id, addon_id):
    subscription = get_object_or_404(BTSubscription, subscription_id=sub_id)
    add_on = get_object_or_404(BTAddOn, addon_id=addon_id)

    try:
        subscribed_add_on = BTSubscribedAddOn.objects.get(
            subscription=subscription,
            add_on=add_on
        )
    except BTSubscribedAddOn.DoesNotExist:
        messages.error(request, _('%(add_on)s is not enabled for %(sub)s') % {
            'add_on': add_on,
            'sub': subscription
        })
        return redirect('payment_index')

    if not subscribed_add_on.is_disableable:
        messages.error(request,
            _('This Add-On cannot be disabled before %(date)s') % {
                'date': formats.date_format(subscribed_add_on.disableable_by)
            }
        )
        return redirect('payment_index')

    result = braintree.Subscription.update(sub_id, {
        'add_ons': {'remove': [str(addon_id)]}
    })

    delete_addon = True

    if result.is_success:
        subscription.import_data(result.subscription)
        subscription.save()
    elif '92016' in (error.code for error in result.errors.deep_errors):
        # Add-On is already deleted on braintree, just delete it locally
        pass
    else:
        delete_addon = False
        messages.error(request, result.message)

    if delete_addon:
        subscribed_add_on.delete()
        messages.success(request, u'Add-On %s successfully disabled' % addon_id)

    return redirect('payment_index')


def add_discount(request, sub_id):
    subscription = get_object_or_404(BTSubscription, subscription_id=sub_id)
    discount_id = request.REQUEST.get('discount_id', '')

    try:
        discount = BTDiscount.objects.get(discount_id=discount_id)
    except BTDiscount.DoesNotExist:
        messages.error(request, _('Sorry, your discount code is invalid'))
        return redirect('payment_index')

    result = braintree.Subscription.update(sub_id, {
        'discounts': {'add': [{'inherited_from_id': discount_id}]}
    })

    if result.is_success:
        discount = BTSubscribedDiscount(
            subscription=subscription,
            discount=discount
        )
        discount.save()

        subscription.import_data(result.subscription)
        subscription.save()
        messages.success(request, u'Discount successfully added')
    else:
        messages.error(request, result.message)

    return redirect('payment_index')


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
        try:
            subscription = BTSubscription.objects.get(
                subscription_id=notification.subscription.id
            )
        except BTSubscription.DoesNotExist:
            subscription = BTSubscription(
                subscription_id=notification.subscription.id,
                customer=card.customer,
            )

        subscription.plan = plan
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
    except BTCreditCard.DoesNotExist:
        log.exception = 'Credit Card not present'
    except BTPlan.DoesNotExist:
        log.exception = 'Plan not present'
    except:
        log.exception = traceback.format_exc()
        # this is bad, reraise error
        raise
    finally:
        log.save()

    return HttpResponse('Ok, thanks')


def error(request):
    return render(request, 'payments/error.html')
