(function() {
  $(function() {
    return $('#card_number').validateCreditCard(function(result) {
      var $card_number = $('#card_number');

      var card_class = null;
      if (result.card_type != null) {
        if (result.card_type.name == 'amex') {
          card_class = 'amex';
        } else if (result.card_type.name == 'visa' ||
                   result.card_type.name == 'visa_electron') {
          card_class = 'visa';
        } else if (result.card_type.name == 'mastercard' ||
                   result.card_type.name == 'maestro') {
          card_class = 'mastercard';
        } else if (result.card_type.name == 'discover') {
          card_class = 'discover';
        }
      }

      $card_number.removeClass().addClass(card_class);

      if (result.length_valid && result.luhn_valid) {
        return $card_number.addClass('valid');
      } else {
        return $card_number.removeClass('valid');
      }
    });
  });

}).call(this);
