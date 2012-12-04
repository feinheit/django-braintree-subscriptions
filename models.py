import braintree
from braintree.exceptions.not_found_error import NotFoundError

from django.db import models
from django.db.models.fields.related import RelatedField, RelatedObject
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.forms.models import model_to_dict
from django.utils.timezone import now


# Common attributes for cached fields
CACHED = {'editable': False, 'blank': True, 'null': True}


def BraintreeSyncedModel(braintree_collection):
    """ A django model for 2-way sync with the braintree vault """

    class BTSyncedModel(models.Model):
        # This is the vault data collection we sync with
        collection = braintree_collection

        # Our timestamps, not to be confused the the braintree timestamps
        created = models.DateTimeField(editable=False, null=True)
        updated = models.DateTimeField(editable=False, null=True)

        # Timestamp are never synced
        always_exclude = ('created', 'updated')

        class Meta:
            get_latest_by = "created"
            abstract = True

        def braintree_key(self):
            """ A represantion of how this instance is indexed in the vault """
            raise NotImplementedError('braintree_key() not implemented')

        def serialize(self, exclude=()):
            """ The shared serialization method """
            data = model_to_dict(self, exclude=self.always_exclude + exclude)
            for key, value in data.iteritems():
                data[key] = unicode(value or '')
            return data

        def serialize_create(self):
            """ When a instance is to be create in the vault """
            return self.serialize()

        def serialize_update(self):
            """ When a instance is to be updated in the vault """
            return self.serialize()

        def on_pushed(self, result):
            """ This is called after a object was pushed into the vault """
            pass

        @classmethod
        def unserialize(cls, data):
            """ Should create a unsaved django object from a vault object """
            pass

        def push(self):
            """ Push this instance into the vault """
            key = self.braintree_key()

            try:
                data = self.serialize_update()
                result = self.collection.update(*key, params=data)
            except (NotFoundError, KeyError):
                data = self.serialize_create()
                result = self.collection.create(data)
                self.created = now()

            if not result.is_success:
                raise ValidationError(result.message)
            else:
                self.on_pushed(result)
                self.updated = now()

        def clean(self):
            """ performs a push on model validation """
            self.push()

        def pull(self):
            """ Pull and sync data from vault into local instance """
            key = self.braintree_key()
            data = self.collection.find(*key)
            self.update(data)

        def update(self, data):
            """ Save the data from the vault into the instance """
            for key, value in data.__dict__.iteritems():
                if hasattr(self, key):
                    field = self._meta.get_field_by_name(key)[0]
                    if issubclass(field.__class__, RelatedObject):
                        self.update_related(field.model, value)
                    elif not issubclass(field.__class__, RelatedField):
                        setattr(self, key, value)
            self.updated = now()
            self.save()

        def update_related(self, related_model, data):
            """ Deal with related objects when imported from pull """
            for object in data:
                try:
                    other = related_model.objects.get(pk=object.id)
                    other.update(object)
                except ObjectDoesNotExist:
                    new = related_model.unserialize(object)
                    if new is not None:
                        new.save()

    @receiver(pre_delete, weak=False)
    def delete_in_vault(sender, instance, **kwargs):
        """ Delete all instance in the vault """
        if issubclass(sender, BTSyncedModel):
            try:
                braintree_collection.delete(*instance.braintree_key())
            except (NotFoundError, KeyError):
                pass

    return BTSyncedModel


def BraintreeMirroredModel(braintree_collection):
    """ A django model that only updates itself from the vault """

    class BTMirroredModel(models.Model):
        # This is the vault data collection we mirror from
        collection = braintree_collection

        class Meta:
            abstract = True

        def braintree_key(self):
            """ A represantion of how this instance is indexed in the vault """
            raise NotImplementedError('braintree_key() not implemented')

        def clean(self):
            try:
                self.import_from_vault()
            except ObjectDoesNotExist:
                self.reset_fields()

        def reset_fields(self):
            for field in self._meta.fields:
                if getattr(field, 'null', False):
                    setattr(self, field.name, None)

        def import_from_vault(self):
            """ Copy data from vault and set on all fields """
            key = self.braintree_key()
            data = None
            if hasattr(self.collection, 'find'):
                try:
                    data = self.collection.find(*key)
                except (NotFoundError, KeyError):
                    pass
            else:
                for obj in self.collection.all():
                    if obj.id == key[0]:
                        data = obj

            if data:
                self.import_data(data)
            else:
                msg = "Object %s not found in vault" % key[0]
                raise ObjectDoesNotExist(msg)

        def import_data(self, data):
            """ How the data from the vault into the instance """
            raise NotImplementedError('import_data(data) not implemented')

    @receiver(pre_delete, weak=False)
    def delete_in_vault(sender, instance, **kwargs):
        """ Delete all instance in the vault """
        if issubclass(sender, BTMirroredModel):
            if hasattr(braintree_collection, 'delete'):
                try:
                    braintree_collection.delete(*instance.braintree_key())
                except (NotFoundError, KeyError):
                    pass

    return BTMirroredModel


class Customer(BraintreeSyncedModel(braintree.Customer)):
    id = models.OneToOneField('customers.Customer',
        related_name='braintree', primary_key=True)

    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    fax = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    website = models.URLField(verify_exists=False, blank=True, null=True)

    def __unicode__(self):
        return self.full_name

    def braintree_key(self):
        return (str(self.id.pk),)

    @property
    def full_name(self):
        return u'%s %s' % (self.first_name, self.last_name)


class Address(BraintreeSyncedModel(braintree.Address)):
    code = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(Customer, related_name='addresses')

    first_name = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    company = models.CharField(max_length=255, blank=True, null=True)
    street_address = models.CharField(max_length=255, blank=True, null=True)
    extended_address = models.CharField(max_length=255, blank=True, null=True)
    locality = models.CharField(max_length=255, blank=True, null=True)
    region = models.CharField(max_length=255, blank=True, null=True)
    postal_code = models.CharField(max_length=255, blank=True, null=True)
    country_code_alpha2 = models.CharField(max_length=255, blank=True, null=True)

    serialize_exclude = ('id',)

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
        address = Address()
        for key, value in data.__dict__.iteritems():
            if hasattr(address, key):
                setattr(address, key, value)
        address.customer_id = int(data.customer_id)
        return address

    def on_pushed(self, result):
        if not self.code == result.address.id:
            self.code = result.address.id


class CreditCard(BraintreeMirroredModel(braintree.CreditCard)):
    token = models.CharField(max_length=100, unique=True)
    customer = models.ForeignKey(Customer, related_name='credit_cards')

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

    # There are more boolean fields in braintree available, yet i don't think
    # We need them for now

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


class Plan(BraintreeMirroredModel(braintree.Plan)):
    plan = models.CharField(max_length=100, unique=True)

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

    def __unicode__(self):
        return self.name if self.name else self.plan

    def braintree_key(self):
        return (self.plan,)

    def import_data(self, data):
        for key, value in data.__dict__.iteritems():
            if hasattr(self, key) and key != 'id':
                setattr(self, key, value)

    @property
    def price_display(self):
        return u'%s %s', (self.price, self.currency_iso_code)
