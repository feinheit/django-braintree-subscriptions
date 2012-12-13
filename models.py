import braintree

from django.db import models
from django.db.models.fields.related import RelatedObject
from django.utils.translation import ugettext_lazy as _

from .sync import BTSyncedModel, BTMirroredModel


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
        return self.get(default=True)


class BTCreditCard(BTMirroredModel):
    collection = braintree.CreditCard

    token = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(BTCustomer, related_name='credit_cards')

    # There should be only one per customer!
    default = models.NullBooleanField(**CACHED)

    bin = models.IntegerField(**CACHED)
    last_4 = models.IntegerField(**CACHED)
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
        for key, value in data.__dict__.iteritems():
            if hasattr(self, key):
                setattr(self, key, value)
        self.customer_id = int(data.customer_id)


class BTPlan(BTMirroredModel):
    collection = braintree.Plan

    plan_id = models.CharField(max_length=100, unique=True)

    name = models.CharField(max_length=100, **CACHED)
    description = models.TextField(**CACHED)
    price = models.DecimalField(max_digits=5, decimal_places=2, **CACHED)
    currency_iso_code = models.CharField(max_length=100, **CACHED)

    billing_day_of_month = models.IntegerField(**CACHED)
    billing_frequency = models.IntegerField(help_text='in months', **CACHED)
    number_of_billing_cycles = models.IntegerField(**CACHED)

    trial_period = models.NullBooleanField(**CACHED)
    trial_duration = models.IntegerField(**CACHED)
    trial_duration_unit = models.CharField(max_length=100, **CACHED)

    # Timestamp from braintree
    created_at = models.DateTimeField(**CACHED)
    updated_at = models.DateTimeField(**CACHED)

    class Meta:
        verbose_name = _('Plan')
        verbose_name_plural = _('Plans')

    def __unicode__(self):
        return self.name if self.name else self.plan_id

    def braintree_key(self):
        return (self.plan_id,)

    def import_data(self, data):
        for key, value in data.__dict__.iteritems():
            if hasattr(self, key) and key != 'id':
                field = self._meta.get_field_by_name(key)[0]
                if not issubclass(field.__class__, RelatedObject):
                    setattr(self, key, value)

    # Addons and Discounts
    def import_related(self, data):
        for key, value in data.__dict__.iteritems():
            if hasattr(self, key) and key != 'id':
                field = self._meta.get_field_by_name(key)[0]
                if issubclass(field.__class__, RelatedObject):
                    field.model.import_related(self, value)

    @property
    def price_display(self):
        return u'%s %s', (self.price, self.currency_iso_code)


class BTAddOn(models.Model):
    plan = models.ForeignKey(BTPlan, related_name='add_ons')
    addon_id = models.CharField(max_length=255, unique=True, **CACHED)

    name = models.CharField(max_length=255, **CACHED)
    description = models.TextField(**CACHED)
    amount = models.DecimalField(max_digits=5, decimal_places=2, **CACHED)
    number_of_billing_cycles = models.IntegerField(**CACHED)

    class Meta:
        verbose_name = _('Add-on')
        verbose_name_plural = _('Add-ons')

    def __unicode__(self):
        return self.name if self.name else self.addon_id

    @classmethod
    def import_related(cls, plan, addons):
        saved_ids = []

        for addon in addons:
            try:
                instance = BTAddOn.objects.get(plan=plan, addon_id=addon.id)
            except BTAddOn.DoesNotExist:
                instance = BTAddOn(plan=plan, addon_id=addon.id)

            for key, value in addon.__dict__.iteritems():
                if hasattr(instance, key) and key != 'id':
                    setattr(instance, key, value)
            instance.save()
            saved_ids.append(instance.id)

        plan.add_ons.exclude(pk__in=saved_ids).delete()


class BTDiscount(models.Model):
    plan = models.ForeignKey(BTPlan, related_name='discounts')
    discount_id = models.CharField(max_length=255, unique=True, **CACHED)

    name = models.CharField(max_length=255, **CACHED)
    description = models.TextField(**CACHED)
    amount = models.DecimalField(max_digits=5, decimal_places=2, **CACHED)
    number_of_billing_cycles = models.IntegerField(**CACHED)

    class Meta:
        verbose_name = _('Discount')
        verbose_name_plural = _('Discounts')

    def __unicode__(self):
        return self.name if self.name else self.discount_id

    @classmethod
    def import_related(cls, plan, discounts):
        saved_ids = []

        for discount in discounts:
            try:
                instance = BTDiscount.objects.get(
                    plan=plan,
                    discount_id=discount.id
                )
            except BTDiscount.DoesNotExist:
                instance = BTDiscount(plan=plan, discount_id=discount.id)

            for key, value in discount.__dict__.iteritems():
                if hasattr(instance, key) and key != 'id':
                    setattr(instance, key, value)
            instance.save()
            saved_ids.append(instance.id)

        # Delte all untouched ids
        plan.discounts.exclude(pk__in=saved_ids).delete()


class BTSubscriptionManager(models.Manager):

    def running(self):
        return self.filter(status__in=('Pending', 'Active', 'Past Due'))


class BTSubscription(BTSyncedModel):
    collection = braintree.Subscription
    pull_excluded_fields = ('id', 'plan_id', 'payment_method_token')

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

    subscription_id = models.CharField(max_length=255)

    customer = models.ForeignKey(BTCustomer, related_name='subscriptions')
    plan = models.ForeignKey(BTPlan, related_name='subscriptions')

    status = models.CharField(max_length=255, choices=STATUS_CHOICES)

    # Overriden details
    price = models.DecimalField(max_digits=5, decimal_places=2, **NULLABLE)
    number_of_billing_cycles = models.IntegerField(**NULLABLE)

    trial_period = models.NullBooleanField()
    trial_duration = models.IntegerField(**NULLABLE)
    trial_duration_unit = models.CharField(max_length=255, **NULLABLE)

    first_billing_date = models.DateField(**NULLABLE)
    billing_day_of_month = models.IntegerField(**NULLABLE)
    start_immediately = models.NullBooleanField()

    objects = BTSubscriptionManager()

    serialize_excluded = ('id', 'customer', 'plan', 'subscription_id', 'status')

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
        data.update({
            'plan_id': self.plan.plan_id,
            'payment_method_token': card.token,
        })
        return data

    def serialize_create(self):
        data = self.serialize_base()
        data.update({
            'options': {
                'do_not_inherit_add_ons_or_discounts': True
            }
        })
        return data

    def serialize_update(self):
        return self.serialize_base()


class BTTransaction(BTMirroredModel):
    SALE = 'sale'
    CREDIT = 'credit'

    TYPE_CHOICES = (
        (SALE, _('Sale')),
        (CREDIT, _('Credit')),
    )

    collection = braintree.Transaction
    skip_import_fields = ('id', 'subscription', 'subscription_id')

    transaction_id = models.CharField(max_length=255)
    subscription = models.ForeignKey(BTSubscription, related_name='transactions')

    amount = models.DecimalField(max_digits=5, decimal_places=2, **CACHED)
    currency_iso_code = models.CharField(max_length=255, **CACHED)
    created_at = models.DateField(**CACHED)
    updated_at = models.DateField(**CACHED)
    status = models.CharField(max_length=255, **CACHED)
    type = models.CharField(max_length=255, **CACHED)

    class Meta:
        verbose_name = _('Transaction')
        verbose_name_plural = _('Transactions')

    def __unicode__(self):
        return self.amount_dislay

    @property
    def amount_dislay(self):
        return u'%s %s' % (self.amount, self.currency_iso_code)

    def braintree_key(self):
        return (self.transaction_id,)

    def import_data(self, data):
        for key, value in data.__dict__.iteritems():
            if hasattr(self, key) and key not in self.skip_import_fields:
                setattr(self, key, value)


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
