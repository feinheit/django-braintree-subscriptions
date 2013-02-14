from django.conf.urls import patterns, url


urlpatterns = patterns('btsubscriptions.views',
    url(
        regex=r'^$',
        view='index',
        name='payment_index'
    ),

    # Credit card management
    url(
        regex=r'^card/add/$',
        view='add_credit_card',
        name='payment_add_credit_card'
    ),
    url(
        regex=r'^card/confirm/$',
        view='confirm_credit_card',
        name='payment_confirm_credit_card'
    ),

    # Subscription management
    url(
        regex=r'^subscribe/(?P<plan_id>\w+)/',
        view='subscribe',
        name="payment_subscribe"
    ),
    url(
        regex=r'^unsubscribe/(?P<subscription_id>\w+)/$',
        view='unsubscribe',
        name='payment_unsubscribe'
    ),

    url(
        regex=r'^multiplesubcriptions/$',
        view='multiple_subscriptions',
        name='payment_multiple_subscriptions'
    ),

    url(
        regex=r'^change_to/(?P<plan_id>\w+)/$',
        view='change_to_plan',
        name='payment_change_to_plan'
    ),
    url(
        regex=r'^downgrade/free/$',
        view='downgrade_to_free_plan',
        name='payment_downgrade_to_free_plan'
    ),

    # Addon Management
    url(
        regex=r'addon/(?P<sub_id>\w+)/enable/(?P<addon_id>\w+)/$',
        view='enable_addon',
        name='payment_enable_addon'
    ),
    url(
        regex=r'addon/(?P<sub_id>\w+)/disable/(?P<addon_id>\w+)/$',
        view='disable_addon',
        name='payment_disable_addon'
    ),

    # Discount Management
    url(
        regex=r'discount/(?P<sub_id>\w+)/add/$',
        view='add_discount',
        name='payment_add_discount'
    ),

    # Webhooks and helper views
    url(
        regex=r'^webhook/$',
        view='webhook',
        name='payment_webhook'
    ),

    url(
        regex=r'^error/$',
        view='error',
        name='payment_error'
    ),
)
