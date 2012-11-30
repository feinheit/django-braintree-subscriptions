import braintree

from django.conf import settings

if settings.BRAINTREE_ENV != 'PRODUCTION':
    BRAINTREE_ENV = braintree.Environment.Sandbox
else:
    BRAINTREE_ENV = braintree.Environment.Production

config = braintree.Configuration.configure(
    BRAINTREE_ENV,
    settings.BRAINTREE_MERCHANT,
    settings.BRAINTREE_PUBLIC_KEY,
    settings.BRAINTREE_PRIVATE_KEY
)