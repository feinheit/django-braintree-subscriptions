
$(function () {
    var $transactions = $('#transactions');
    var $transactions_toggle = $('#transactions-toggle');

    $transactions.on('shown', function () {
        $transactions_toggle.find('.whenshown').show();
        $transactions_toggle.find('.whenhidden').hide();
        $transactions_toggle.addClass('dropup');
    });

    $transactions.on('hidden', function () {
        $transactions_toggle.find('.whenshown').hide();
        $transactions_toggle.find('.whenhidden').show();
        $transactions_toggle.removeClass('dropup');
    });

    $transactions_toggle.click(function () {
        $transactions.collapse('toggle');
    });

    $transactions.collapse('hide');

})