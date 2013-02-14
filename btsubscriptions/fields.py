import datetime

from django.forms.fields import CharField, ChoiceField, RegexField
from django.forms import ValidationError
from django.utils.checksums import luhn
from django.utils.translation import gettext as _


class CreditCardField(CharField):
    """ Form field validation credit card numbers """

    default_error_messages = {
        'invalid': _('The credit card number you entered is invalid.')
    }

    def clean(self, value):
        super(CreditCardField, self).clean(value)

        value = value.strip().replace(' ', '')

        if not luhn(value):
            raise ValidationError(self.error_messages['invalid'])

        return value


class ExpiryMonthField(ChoiceField):
    """ Expiration field for month """

    def __init__(self, *args, **kwargs):
        month_choices = [(i, '%02d' % i) for i in xrange(1, 13)]
        super(ExpiryMonthField, self).__init__(month_choices, *args, **kwargs)

class ExpiryYearField(ChoiceField):
    """ Expiration field for year """

    def __init__(self, *args, **kwargs):
        current_year = datetime.date.today().year
        year_choices = [(i, i) for i in range(current_year, current_year + 10)]
        super(ExpiryYearField, self).__init__(year_choices, *args, **kwargs)


class CVVField(CharField):
    """ Card Verification Value Field """

    default_error_messages = {
        'invalid': _('The verification value you entered is invalid.'),
    }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('min_length', 3)
        kwargs.setdefault('max_length', 4)
        super(CVVField, self).__init__(*args, **kwargs)