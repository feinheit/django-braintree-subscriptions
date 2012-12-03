(function() {
  $(function() {

    $('input').not('#card_number').keyup(function () {
      var $group = $(this).parents('.control-group');

      var all_valid = true;
      $group.find('input').each(function(i, e) {
          if (!e.validity.valid || !$(e).val()) {
            all_valid = false;
            return false;
          }
      })

      if(all_valid) {
        $group.addClass('success');
      } else {
        $group.removeClass('success');
      }
    });

    $('#card_number').validateCreditCard(function(result) {
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
        return $('#card_control').addClass('success');
      } else {
        return $('#card_control').removeClass('success');
      }
    });
  });

}).call(this);
