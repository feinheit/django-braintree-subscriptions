from django import forms
from django.contrib import admin

from .models import Customer, Address, CreditCard, Plan


class AddressInlineAdmin(admin.StackedInline):
    model = Address
    extra = 0


class CreditCardInline(admin.StackedInline):
    model = CreditCard
    extra = 0
    readonly_fields = (
        'default',
        'bin',
        'last_4',
        'cardholder_name',
        'expiration_month',
        'expiration_year',
        'expiration_date',
        'masked_number',
        'unique_number_identifier',
        'country_of_issuance',
        'issuing_bank',
    )


class CustomerAdmin(admin.ModelAdmin):
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
    actions = ('pull',)

    def pull(self, request, queryset):
        for instance in queryset:
            instance.pull()
    pull.short_description = 'Pull data from braintree'


class PlanAdminForm(forms.ModelForm):
    class Meta:
        model = Plan
        exclude = ('name',)


class PlanAdmin(admin.ModelAdmin):
    form = PlanAdminForm
    list_display = ('name', 'price', 'currency_iso_code')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return (
                'name',
                'description',
                'price',
                'currency_iso_code',
                'billing_day_of_month',
                'billing_frequency',
                'number_of_billing_cycles',
                'trial_period',
                'trial_duration',
                'trial_duration_unit',
                'created_at',
                'updated_at'
            )
        else:
            return ()


admin.site.register(Customer, CustomerAdmin)
admin.site.register(Plan, PlanAdmin)
