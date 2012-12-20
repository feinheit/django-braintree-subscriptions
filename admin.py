from django import forms
from django.db.models import TextField
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

import braintree

import models


class BTSyncedModelAdminMixin(object):
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
                form.instance.pull_related()
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


class BTMirroredModelAdminMixin(object):
    def get_readonly_fields(self, request, obj=None):
        """ show all cached fields as readonly in admin """
        if hasattr(self, '_readonly_fields'):
            return self._readonly_fields
        self._readonly_fields = []

        excluded = getattr(self, 'readonly_excluded_fields', [])

        for field in self.model._meta.fields:
            if field.null and not field.editable and not field.name in excluded:
                self._readonly_fields.append(field.name)

        return self._readonly_fields

    def save_model(self, request, obj, form, change):
        obj.pull()
        obj.save()

    def delete_model(self, request, obj):
        obj.delete_from_vault()
        obj.delete()


class BTAddressInlineAdmin(BTSyncedModelAdminMixin, admin.StackedInline):
    model = models.BTAddress
    readonly_fields = ('code',)
    extra = 0


class BTCreditCardInline(BTMirroredModelAdminMixin, admin.StackedInline):
    model = models.BTCreditCard
    extra = 0


class BTCustomerAdmin(BTSyncedModelAdminMixin, admin.ModelAdmin):
    list_display = (
        'first_name',
        'last_name',
        'company',
        'email',
        'fax',
        'phone',
        'website'
    )
    inlines = (BTAddressInlineAdmin, BTCreditCardInline)
    raw_id_fields = ('id',)
    readonly_fields = ('created', 'updated')
    actions = ('bt_pull',)


class BTAddOnAdmin(BTMirroredModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'description', 'amount')


class BTDiscountAdmin(BTMirroredModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'description', 'amount')


class BTPlanAdmin(BTMirroredModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'price', 'currency_iso_code')
    actions = ('import_all',)

    def import_all(self, request, queryset):
        import braintree
        plans = braintree.Plan.all()
        for plan in plans:
            plan, created = models.Plan.objects_get_or_create(plan_id=plan.id)
            plan.import_data(plan)
            plan.import_related(plan)
            plan.save()


class BTTransactionInlineAdmin(BTMirroredModelAdminMixin, admin.TabularInline):
    model = models.BTTransaction
    readonly_excluded_fields = ('updated_at',)
    extra = 0


class BTSubscriptionAdmin(BTSyncedModelAdminMixin, admin.ModelAdmin):
    list_display = (
        'subscription_id',
        'status',
        'customer',
        'plan'
    )
    list_filter = ('plan', 'status')
    readonly_fields = ('subscription_id', 'status', 'data')
    filter_horizontal = ('add_ons', 'discounts')
    inlines = [BTTransactionInlineAdmin]
    actions = ('cancel_subscriptions',)

    def cancel_subscriptions(self, request, queryset):
        for subscription in queryset:
            subscription.cancel()

    def save_related(self, request, form, formsets, change):
        form.save_m2m()
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

        if change:
            sub = form.instance

            addons = [
                {'inherited_from_id': a.addon_id} for a in sub.add_ons.all()
            ]

            discounts = [
                {'inherited_from_id': a.discount_id} for a in sub.discounts.all()
            ]

            result = braintree.Subscription.update(sub.subscription_id, {
                "options": {
                    "replace_all_add_ons_and_discounts": True
                },
                "add_ons": {"add": addons},
                "discounts": {"add": discounts}
            })

            if result.is_success:
                messages.info(request, _('Add-Ons and Discounts updated'))
            else:
                messages.error(request, result.message)


class BTWebhookLogAdmin(admin.ModelAdmin):
    readonly_fields = ('received',)
    formfield_overrides = {
        TextField: {'widget': forms.Textarea(attrs={'cols': 120, 'rows': 30})},
    }

admin.site.register(models.BTCustomer, BTCustomerAdmin)
admin.site.register(models.BTPlan, BTPlanAdmin)
admin.site.register(models.BTAddOn, BTAddOnAdmin)
admin.site.register(models.BTDiscount, BTDiscountAdmin)
admin.site.register(models.BTSubscription, BTSubscriptionAdmin)

admin.site.register(models.BTWebhookLog, BTWebhookLogAdmin)
