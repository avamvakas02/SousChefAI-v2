/**
 * Account settings: destructive-action confirmations.
 */
(function () {
    'use strict';

    function initConfirmForms() {
        document.querySelectorAll('form[data-confirm-message]').forEach(function (form) {
            form.addEventListener('submit', function (e) {
                var msg = form.getAttribute('data-confirm-message');
                if (msg && !window.confirm(msg)) {
                    e.preventDefault();
                }
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initConfirmForms);
    } else {
        initConfirmForms();
    }
}());
