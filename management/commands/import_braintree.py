from django.core.management.base import NoArgsCommand

from ...models import BTPlan, BTAddOn, BTDiscount


class Command(NoArgsCommand):
    help = 'Import all mirrored models from the braintree vault'

    def import_from_vault(self, model, btkeyname):
        for object in model.collection.all():
            key = {}
            key[btkeyname] = object.id
            try:
                btobject = model.objects.get(**key)
                print u"Updating",
            except model.DoesNotExist:
                btobject = model(**key)
                print u"Importing",

            print u"%s %s" % (model._meta.verbose_name.lower(), object.id)

            btobject.import_data(object)
            btobject.save()

    def handle_noargs(self, **options):
        self.import_from_vault(BTPlan, 'plan_id')
        self.import_from_vault(BTAddOn, 'addon_id')
        self.import_from_vault(BTDiscount, 'discount_id')
