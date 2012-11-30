

from django import forms

from .fields import CreditCardField, ExpiryMonthField, ExpiryYearField, CVVField


class CreditCardForm(forms.Form):

    cardholder_name = forms.CharField()
    creditcard_number = CreditCardField()
    expiration_month = ExpiryMonthField()
    expiration_year = ExpiryYearField()
    validation_code = CVVField()


class ExpiryForm(forms.Form):

    expiration_month = ExpiryMonthField()
    expiration_year = ExpiryYearField()


class TransactionForm(CreditCardForm):

    amount = forms.DecimalField()
