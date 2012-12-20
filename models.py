import braintree

from datetime import timedelta

from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from .sync import BTSyncedModel, BTMirroredModel

from jsonfield import JSONField

# Common attributes sets for fields
NULLABLE = {'blank': True, 'null': True}
CACHED = {'editable': False, 'blank': True, 'null': True}


class BTCustomer(BTSyncedModel):
    collection = braintree.Customer

    id = models.OneToOneField('customers.Customer',
        related_name='braintree', primary_key=True)

    first_name = models.CharField(max_length=255, **NULLABLE)
    last_name = models.CharField(max_length=255, **NULLABLE)
    company = models.CharField(max_length=255, **NULLABLE)
    email = models.EmailField(**NULLABLE)
    fax = models.CharField(max_length=255, **NULLABLE)
    phone = models.CharField(max_length=255, **NULLABLE)
    website = models.URLField(**NULLABLE)

    plans = models.ManyToManyField('BTPlan', through='BTSubscription',
        related_name='customers')

    class Meta:
        verbose_name = _('Customer')
        verbose_name_plural = _('Customers')

    def __unicode__(self):
        return self.full_name

    def braintree_key(self):
        return (str(self.id.pk),)

    def push_related(self):
        for address in self.addresses.all():
            address.push()
            address.save()

    @property
    def full_name(self):
        return u'%s %s' % (self.first_name, self.last_name)


class BTAddress(BTSyncedModel):
    collection = braintree.Address

    code = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(BTCustomer, related_name='addresses')

    first_name = models.CharField(max_length=255, **NULLABLE)
    last_name = models.CharField(max_length=255, **NULLABLE)
    company = models.CharField(max_length=255, **NULLABLE)
    street_address = models.CharField(max_length=255, **NULLABLE)
    extended_address = models.CharField(max_length=255, **NULLABLE)
    locality = models.CharField(max_length=255, **NULLABLE)
    region = models.CharField(max_length=255, **NULLABLE)
    postal_code = models.CharField(max_length=255, **NULLABLE)
    country_code_alpha2 = models.CharField(max_length=255, **NULLABLE)

    serialize_exclude = ('id',)

    class Meta:
        verbose_name = _('Address')
        verbose_name_plural = _('Addresses')
        get_latest_by = 'created'

    def __unicode__(self):
        return self.code

    def braintree_key(self):
        return (str(self.customer.pk), self.code or '0')

    def serialize_create(self):
        data = self.serialize(exclude=('id', 'code', 'customer'))
        data['customer_id'] = str(self.customer.pk)
        return data

    def serialize_update(self):
        return self.serialize(exclude=('id', 'code', 'customer'))

    @classmethod
    def unserialize(cls, data):
        address = BTAddress()
        for key, value in data.__dict__.iteritems():
            if hasattr(address, key):
                setattr(address, key, value)
        address.customer_id = int(data.customer_id)
        return address

    def on_pushed(self, result):
        if not self.code == result.address.id:
            self.code = result.address.id


class BTCreditCardManager(models.Manager):

    def has_default(self):
        return self.filter(default=True).count() == 1

    def get_default(self):
        try:
            return self.get(default=True)
        except self.model.DoesNotExist:
            return None


class BTCreditCard(BTMirroredModel):
    collection = braintree.CreditCard
    pull_excluded_fields = ('id', 'customer_id')

    token = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(BTCustomer, related_name='credit_cards')

    # There should be only one per customer!
    default = models.NullBooleanField(**CACHED)

    bin = models.CharField(max_length=255, **CACHED)
    last_4 = models.CharField(max_length=255, **CACHED)
    cardholder_name = models.CharField(max_length=255, **CACHED)
    expiration_month = models.IntegerField(**CACHED)
    expiration_year = models.IntegerField(**CACHED)
    expiration_date = models.CharField(max_length=255, **CACHED)
    masked_number = models.CharField(max_length=255, **CACHED)
    unique_number_identifier = models.CharField(max_length=255, **CACHED)

    country_of_issuance = models.CharField(max_length=255, **CACHED)
    issuing_bank = models.CharField(max_length=255, **CACHED)

    objects = BTCreditCardManager()

    # There are more boolean fields in braintree available, yet i don't think
    # We need them for now

    class Meta:
        verbose_name = _('Credit Card')
        verbose_name_plural = _('Credit Cards')

    def __unicode__(self):
        return self.mask

    @property
    def mask(self):
        if self.masked_number:
            return self.masked_number
        elif self.bin and self.last_4:
            return '%s******%s' % (self.bin, self.last_4)
        else:
            return self.token

    def braintree_key(self):
        return (self.token or '0',)

    def import_data(self, data):
        super(BTCreditCard, self).import_data(data)
        self.customer_id = int(data.customer_id)


class BTPlan(BTMirroredModel):
    collection = braintree.Plan

    plan_id = models.CharField(max_length=100, unique=True)

    name = models.CharField(max_length=100, **CACHED)
    description = models.TextField(**CACHED)
    price = models.DecimalField(max_digits=10, decimal_places=2, **CACHED)
    currency_iso_code = models.CharField(max_length=100, **CACHED)

    billing_day_of_month = models.IntegerField(**CACHED)
    billing_frequency = models.IntegerField(help_text='in months', **CACHED)
    number_of_billing_cycles = models.IntegerField(**CACHED)

    trial_period = models.NullBooleanField(**CACHED)
    trial_duration = models.IntegerField(**CACHED)
    trial_duration_unit = models.CharField(max_length=100, **CACHED)

    #add_ons = models.ManyToManyField('BTAddOn', related_name='plans')
    #discounts = models.ManyToManyField('BTDiscount', related_name='plans')

    # Timestamp from braintree
    created_at = models.DateTimeField(**CACHED)
    updated_at = models.DateTimeField(**CACHED)

    class Meta:
        verbose_name = _('Plan')
        verbose_name_plural = _('Plans')
        ordering = ('-price',)

    def __unicode__(self):
        return self.name if self.name else self.plan_id

    def braintree_key(self):
        return (self.plan_id,)

    @property
    def price_display(self):
        return u'%s %s', (self.price, self.currency_iso_code)


class BTAddOn(BTMirroredModel):
    collection = braintree.AddOn
    #plan = models.ForeignKey(BTPlan, related_name='add_ons')
    addon_id = models.CharField(max_length=255, unique=True)

    name = models.CharField(max_length=255, **CACHED)
    description = models.TextField(**CACHED)
    amount = models.DecimalField(max_digits=10, decimal_places=2, **CACHED)
    number_of_billing_cycles = models.IntegerField(**CACHED)

    class Meta:
        verbose_name = _('Add-on')
        verbose_name_plural = _('Add-ons')

    def __unicode__(self):
        return self.name if self.name else self.addon_id

    def braintree_key(self):
        return (self.addon_id,)


class BTDiscount(BTMirroredModel):
    collection = braintree.Discount
    #plan = models.ForeignKey(BTPlan, related_name='discounts')
    discount_id = models.CharField(max_length=255, unique=True)

    name = models.CharField(max_length=255, **CACHED)
    description = models.TextField(**CACHED)
    amount = models.DecimalField(max_digits=10, decimal_places=2, **CACHED)
    number_of_billing_cycles = models.IntegerField(**CACHED)

    class Meta:
        verbose_name = _('Discount')
        verbose_name_plural = _('Discounts')

    def __unicode__(self):
        return self.name if self.name else self.discount_id

    def braintree_key(self):
        return (self.discount_id,)


class BTSubscriptionManager(models.Manager):

    def running(self):
        return self.filter(status__in=('Pending', 'Active', 'Past Due'))


class BTSubscription(BTSyncedModel):
    collection = braintree.Subscription
    pull_excluded_fields = (
        'id',
        'plan_id',
        'payment_method_token',
        'add_ons',
        'discounts'
    )

    PENDING = 'Pending'
    ACTIVE = 'Active'
    PAST_DUE = 'Past Due'
    EXPIRED = 'Expired'
    CANCELED = 'Canceled'

    STATUS_CHOICES = (
        (PENDING, _('Pending')),
        (ACTIVE, _('Active')),
        (PAST_DUE, _('Past Due')),
        (EXPIRED, _('Expired')),
        (CANCELED, _('Canceled'))
    )

    subscription_id = models.CharField(max_length=255, unique=True)

    customer = models.ForeignKey(BTCustomer, related_name='subscriptions')
    plan = models.ForeignKey(BTPlan, related_name='subscriptions')

    price = models.DecimalField(max_digits=10, decimal_places=2, **NULLABLE)
    number_of_billing_cycles = models.IntegerField(
        help_text=_('Leave empty for endless subscriptions'), **NULLABLE)

    status = models.CharField(max_length=255, choices=STATUS_CHOICES)
    data = JSONField(**NULLABLE)

    add_ons = models.ManyToManyField(BTAddOn, through='BTSubscribedAddOn',
        related_name='subscriptions', **NULLABLE)
    discounts = models.ManyToManyField(BTDiscount, through='BTSubscribedDiscount',
        related_name='subscriptions', **NULLABLE)

    objects = BTSubscriptionManager()

    serialize_excluded = (
        'id',
        'customer',
        'plan',
        'subscription_id',
        'status',
        'data'
    )

    updateable_fields = (
        'plan_id',
        'payment_method_token',
        'price',
        'number_of_billing_cycles',
        'never_expires'
    )

    class Meta:
        verbose_name = _('Subscription')
        verbose_name_plural = _('Subscriptions')

    def __unicode__(self):
        return self.subscription_id

    def cancel(self):
        """ Cancel this subscription instantly """
        result = self.collection.cancel(self.subscription_id)
        if result.is_success:
            self.status = BTSubscription.CANCELED
            self.save()
        return result

    def braintree_key(self):
        return (self.subscription_id,)

    def pull_related(self):
        for transaction in self.transactions.all():
            transaction.pull()
            transaction.save()

    def on_pushed(self, result):
        self.subscription_id = result.subscription.id
        self.status = result.subscription.status

    def serialize_base(self):
        # Intentionally raise DoesNotExist here if 0 or >1 default cards
        card = self.customer.credit_cards.get_default()
        data = self.serialize(exclude=self.serialize_excluded)

        if not self.number_of_billing_cycles:
            data['never_expires'] = True

        data.update({
            'plan_id': self.plan.plan_id,
            'payment_method_token': card.token,
        })

        return data

    def serialize_create(self):
        return self.serialize_base()

    def serialize_update(self):
        data = self.serialize_base()

        for key in data.keys():
            if key not in self.updateable_fields:
                data.pop(key, None)

        data.update({
            "options": {
                "prorate_charges": True
            }
        })
        return data

    def import_data(self, data):
        super(BTSubscription, self).import_data(data)
        # TODO: UGLY, fix this
        data_dict = data.__dict__.copy()
        for k in ('gateway', 'transactions', 'descriptor', 'add_ons', 'discounts'):
            data_dict.pop(k, None)
        self.data = data_dict

    @property
    def next_billing_amount(self):
        if 'next_billing_period_amount' in self.data:
            next_amount = self.data['next_billing_period_amount']
            balance = self.data.get('balance', 0.0)
            return max(balance + next_amount, 0.0)
        else:
            return _('Unknown')


class BTSubscribedAddOn(models.Model):
    subscription = models.ForeignKey(BTSubscription,
        related_name='subscribed_addons')
    add_on = models.ForeignKey(BTAddOn,
        related_name='subscribed_addons')

    quantity = models.IntegerField(default=1)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Subscribed add-on')
        verbose_name_plural = _('Subscribed add-ons')
        unique_together = (('subscription', 'add_on'),)

    def __unicode__(self):
        return u'%s -> %s' % (self.subscription, self.add_on)

    @property
    def disableable_by(self):
        return (self.created + timedelta(days=30)).date()

    @property
    def is_disableable(self):
        return now().date() >= self.disableable_by


class BTSubscribedDiscount(models.Model):
    subscription = models.ForeignKey(BTSubscription,
        related_name='subscribed_discounts')
    discount = models.ForeignKey(BTDiscount,
        related_name='subscribed_discounts')

    quantity = models.IntegerField(default=1)

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Subscribed discount')
        verbose_name_plural = _('Subscribed discounts')
        unique_together = (('subscription', 'discount'),)

    def __unicode__(self):
        return u'%s -> %s' % (self.subscription, self.discount)


class BTTransactionManager(models.Manager):

    def for_customer(self, customer):
        return self.filter(subscription__customer=customer)


class BTTransaction(BTMirroredModel):
    SALE = 'sale'
    CREDIT = 'credit'

    TYPE_CHOICES = (
        (SALE, _('Sale')),
        (CREDIT, _('Credit')),
    )

    collection = braintree.Transaction
    pull_excluded_fields = ('id', 'subscription', 'subscription_id')

    transaction_id = models.CharField(max_length=255, unique=True)
    subscription = models.ForeignKey(BTSubscription, related_name='transactions')

    amount = models.DecimalField(max_digits=10, decimal_places=2, **CACHED)
    currency_iso_code = models.CharField(max_length=255, **CACHED)

    credit_card = models.CharField(max_length=100, **CACHED)

    created_at = models.DateTimeField(**CACHED)
    updated_at = models.DateTimeField(**CACHED)

    status = models.CharField(max_length=255, **CACHED)
    type = models.CharField(max_length=255, **CACHED)

    objects = BTTransactionManager()

    class Meta:
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')
        ordering = ('-created_at',)

    def __unicode__(self):
        return self.amount_display

    @property
    def amount_display(self):
        return u'%s %s' % (self.amount, self.currency_iso_code)

    def braintree_key(self):
        return (self.transaction_id,)

    def import_data(self, data):
        super(BTTransaction, self).import_data(data)
        self.credit_card = u'%(bin)s******%(last_4)s' % data.credit_card


class BTWebhookLog(models.Model):
    """ A log of received webhook notficiations. Purley for debugging """

    received = models.DateTimeField(auto_now=True)
    kind = models.CharField(max_length=255)
    data = models.TextField(blank=True)
    exception = models.TextField(blank=True)

    class Meta:
        verbose_name = _('WebhookLog')
        verbose_name_plural = _('WebhookLogs')

    def __unicode__(self):
        return self.kind
