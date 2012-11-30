from django import forms
from django.contrib import admin

from .models import Customer, Address

class AddressForm(forms.ModelForm):
    id = forms.CharField(required=False, widget= forms.TextInput(attrs={
        'readonly': True,
        'style': 'border: none;',
        'placeholder': None
    }))

    class Meta:
        model = Address

    def clean_id(self):
        return self.instance.id

class AddressInlineAdmin(admin.StackedInline):
    model = Address
    form = AddressForm
    extra = 0

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
    inlines = (AddressInlineAdmin,)
    raw_id_fields = ('id',)
    readonly_fields = ('created', 'updated')
    actions = ('pull',)

    def pull(self, request, queryset):
        for instance in queryset:
            instance.pull()
    pull.short_description = 'Pull data from braintree'

admin.site.register(Customer, CustomerAdmin)