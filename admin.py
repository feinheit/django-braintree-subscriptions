from django import forms
from django.contrib import admin

from .models import Customer, Address, CreditCard

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

admin.site.register(Customer, CustomerAdmin)