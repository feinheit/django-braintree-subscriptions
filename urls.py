from django.conf.urls import patterns, url


urlpatterns = patterns('keetab_cp.payments.views',
    url(r'^$', 'index',
        name='payment_index'),

    url(r'card/add/$', 'add_credit_card',
        name='payment_add_credit_card'),
    url(r'card/confirm/$', 'confirm_credit_card',
        name='payment_confirm_credit_card'),
    url(r'card/(?P<token>[-\w]+)/delete/$', 'delete_credit_card',
        name='payment_delete_credit_card'),

    #url(r'subscribe/(?P<plan_id>\w+)/', 'subscribe_to_plan', name="payment_subscribe_to_plan"),
    #url(r'unsubscribe/$', 'unsubscribe', name='payment_unsubscribe'),

    url(r'error/$', 'error', name='payment_error'),
)
