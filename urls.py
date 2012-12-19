from django.conf.urls import patterns, url


urlpatterns = patterns('keetab_cp.payments.views',
    url(
        regex=r'^$',
        view='index',
        name='payment_index'
    ),

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
