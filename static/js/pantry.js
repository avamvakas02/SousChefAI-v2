/**
 * Pantry list and zone catalog–specific behavior.
 */
(function () {
    'use strict';

    var searchInput = document.getElementById('pantry-catalog-search');
    var groups = Array.prototype.slice.call(document.querySelectorAll('[data-catalog-group]'));
    var controls = document.querySelector('[data-catalog-controls]');
    var showMoreBtn = document.getElementById('pantry-show-more-btn');
    var items = Array.prototype.slice.call(document.querySelectorAll('[data-catalog-item]'));
    var initialVisible = controls ? parseInt(controls.getAttribute('data-initial-visible'), 10) : 50;
    var showMoreStep = controls ? parseInt(controls.getAttribute('data-show-more-step'), 10) : 16;
    var revealedCount = Number.isFinite(initialVisible) && initialVisible > 0 ? initialVisible : 50;

    if (!searchInput || !groups.length || !items.length) {
        return;
    }

    if (!Number.isFinite(showMoreStep) || showMoreStep < 1) {
        showMoreStep = 16;
    }

    function updateAllGroups() {
        var query = (searchInput.value || '').trim().toLowerCase();
        var totalMatches = 0; // items matching filter
        var totalVisible = 0; // items currently rendered
        var visibleSlotsUsed = 0;

        items.forEach(function (item) {
            var name = (item.getAttribute('data-name') || '').toLowerCase();
            var matches = !query || name.indexOf(query) !== -1;
            var show = false;

            if (matches) {
                totalMatches += 1;
                if (query) {
                    show = true;
                } else if (visibleSlotsUsed < revealedCount) {
                    show = true;
                    visibleSlotsUsed += 1;
                }
            }

            item.classList.toggle('d-none', !show);
            if (show) {
                totalVisible += 1;
            }
        });

        groups.forEach(function (group) {
            var groupItems = Array.prototype.slice.call(group.querySelectorAll('[data-catalog-item]'));
            var groupHasVisible = groupItems.some(function (item) {
                return !item.classList.contains('d-none');
            });
            group.classList.toggle('d-none', !groupHasVisible);
        });

        if (!showMoreBtn) {
            return;
        }

        if (query) {
            showMoreBtn.classList.add('d-none');
            return;
        }

        showMoreBtn.classList.remove('d-none');
        if (totalVisible >= totalMatches) {
            showMoreBtn.disabled = true;
            showMoreBtn.textContent = 'All ingredients shown';
        } else {
            showMoreBtn.disabled = false;
            showMoreBtn.textContent = 'Show more';
        }
    }

    if (showMoreBtn) {
        showMoreBtn.addEventListener('click', function () {
            revealedCount += showMoreStep;
            updateAllGroups();
        });
    }

    searchInput.addEventListener('input', updateAllGroups);
    updateAllGroups();
}());
