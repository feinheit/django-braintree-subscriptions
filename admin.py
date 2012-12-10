from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError

import models


class SyncedBraintreeModelAdminMixin(object):
    def save_model(self, request, obj, form, change):
        try:
            obj.push()
            obj.save()
        except ValidationError as e:
            msg = u'Braintree push error: %s' % e.messages[0]
            messages.error(request, msg)

    def save_related(self, request, form, formsets, change):
        form.save_m2m()
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

        if form.instance:
            try:
                form.instance.push_related()
            except ValidationError as e:
                msg = u'Braintree push error: %s' % e.messages[0]
                messages.error(request, msg)

    def delete_model(self, request, obj):
        obj.delete_from_vault()
        obj.delete()

    def bt_pull(self, request, queryset):
        for instance in queryset:
            instance.pull()
    bt_pull.short_description = 'Pull data from braintree'


class MirroredBrainteeModelAdminMixin(object):
    def get_readonly_fields(self, request, obj=None):
        """ show all cached fields as readonly in admin """
        if hasattr(self, '_readonly_fields'):
            return self._readonly_fields
        self._readonly_fields = []

        for field in self.model._meta.fields:
            if field.null and not field.editable:
                self._readonly_fields.append(field.name)

        return self._readonly_fields

    def save_model(self, request, obj, form, change):
        obj.pull()
        obj.save()

    def delete_model(self, request, obj):
        obj.delete_from_vault()
        obj.delete()

    def save_related(self, request, form, formsets, change):
        form.save_m2m()
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

        if form.instance:
            form.instance.pull_related()


class AddressInlineAdmin(SyncedBraintreeModelAdminMixin, admin.StackedInline):
    model = models.Address
    readonly_fields = ('code',)
    extra = 0


class CreditCardInline(MirroredBrainteeModelAdminMixin, admin.StackedInline):
    model = models.CreditCard
    extra = 0


class CustomerAdmin(SyncedBraintreeModelAdminMixin, admin.ModelAdmin):
    list_display = (
        'first_name',
        'last_name',
        'company',
        'email',
        'fax',
        'phone',
        'website'
    )
    inlines = (AddressInlineAdmin, CreditCardInline)
    raw_id_fields = ('id',)
    readonly_fields = ('created', 'updated')
    actions = ('bt_pull',)


class AddOnInline(MirroredBrainteeModelAdminMixin, admin.StackedInline):
    model = models.AddOn

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj):
        return False


class DiscountInline(MirroredBrainteeModelAdminMixin, admin.StackedInline):
    model = models.Discount

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj):
        return False


class PlanAdmin(MirroredBrainteeModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'price', 'currency_iso_code')
    inlines = (AddOnInline, DiscountInline)


class SubscriptionAdmin(SyncedBraintreeModelAdminMixin, admin.ModelAdmin):
    list_filter = ('plan_id',)
    readonly_fields = ('subscription_id',)

admin.site.register(models.Customer, CustomerAdmin)
admin.site.register(models.Plan, PlanAdmin)
admin.site.register(models.Subscription, SubscriptionAdmin)
