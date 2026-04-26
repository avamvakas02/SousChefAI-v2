/**
 * Login & register: password visibility, strength meter, confirm match.
 */
(function () {
    'use strict';

    function fieldSelector(fieldId) {
        return '#' + fieldId;
    }

    function togglePassword(fieldId) {
        var field = document.querySelector(fieldSelector(fieldId));
        if (!field) return false;
        field.type = field.type === 'password' ? 'text' : 'password';
        return field.type === 'text';
    }

    window.togglePassword = togglePassword;

    function bindPasswordToggles() {
        document.querySelectorAll('.input-toggle[data-password-target]').forEach(function (el) {
            var targetId = el.getAttribute('data-password-target');
            if (!targetId) return;
            var icon = el.querySelector('img');

            function updateToggleIcon(isVisible) {
                if (!icon || !icon.src) return;
                var nextIcon = isVisible ? 'visible.png' : 'hidden.png';
                icon.src = icon.src.replace(/(hidden|visible)\.png$/, nextIcon);
            }

            el.addEventListener('click', function () {
                var isVisible = togglePassword(targetId);
                updateToggleIcon(isVisible);
            });
            el.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    var isVisible = togglePassword(targetId);
                    updateToggleIcon(isVisible);
                }
            });
        });
    }

    function initRegisterStrength() {
        var regPass = document.querySelector('#registerPassword');
        if (!regPass) return;

        regPass.addEventListener('input', function () {
            var val = this.value;
            var bar = document.querySelector('#strengthBar');
            var text = document.querySelector('#strengthText');
            if (!bar || !text) return;

            var strength = 0;
            if (val.length >= 8) strength += 1;
            if (/[A-Z]/.test(val)) strength += 1;
            if (/[0-9]/.test(val)) strength += 1;
            if (/[^A-Za-z0-9]/.test(val)) strength += 1;

            var levels = ['', 'weak', 'fair', 'good', 'strong'];
            var labels = ['', 'Weak', 'Fair', 'Good', 'Strong'];
            bar.className = 'strength-bar ' + (levels[strength] || '');
            text.textContent = labels[strength] || '';
        });
    }

    function initConfirmMatch() {
        var confirmField = document.querySelector('#confirmPassword');
        if (!confirmField) return;

        confirmField.addEventListener('input', function () {
            var pass1 = document.querySelector('#registerPassword');
            var indicator = document.querySelector('#matchIndicator');
            if (!indicator) return;
            var v1 = pass1 ? pass1.value : '';
            if (this.value === '') {
                indicator.textContent = '';
            } else if (this.value === v1) {
                indicator.textContent = '✓';
            } else {
                indicator.textContent = '✗';
            }
        });
    }

    function init() {
        bindPasswordToggles();
        initRegisterStrength();
        initConfirmMatch();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
