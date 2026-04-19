/**
 * Pantry list and zone catalog-specific behavior.
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

(function () {
    'use strict';

    var searchInput = document.getElementById('pantry-home-catalog-search');
    var groups = Array.prototype.slice.call(document.querySelectorAll('[data-home-catalog-group]'));
    var items = Array.prototype.slice.call(document.querySelectorAll('[data-home-catalog-item]'));
    var hintEl = document.getElementById('pantry-home-search-hint');
    var emptyEl = document.getElementById('pantry-home-search-empty');

    if (!searchInput || !items.length || !groups.length) {
        return;
    }

    function updateHomeQuickCatalog() {
        var query = (searchInput.value || '').trim().toLowerCase();
        var totalMatches = 0;
        var hasQuery = query.length > 0;

        items.forEach(function (item) {
            var name = (item.getAttribute('data-name') || '').toLowerCase();
            var matches = hasQuery && name.indexOf(query) !== -1;
            if (matches) {
                totalMatches += 1;
            }
            item.classList.toggle('d-none', !matches);
        });

        groups.forEach(function (group) {
            var groupItems = Array.prototype.slice.call(group.querySelectorAll('[data-home-catalog-item]'));
            var groupHasVisible = hasQuery && groupItems.some(function (item) {
                return !item.classList.contains('d-none');
            });
            group.classList.toggle('d-none', !groupHasVisible);
        });

        if (hintEl) {
            hintEl.classList.toggle('d-none', hasQuery);
        }
        if (emptyEl) {
            emptyEl.classList.toggle('d-none', !hasQuery || totalMatches > 0);
        }
    }

    searchInput.addEventListener('input', updateHomeQuickCatalog);
    updateHomeQuickCatalog();
}());

(function () {
    'use strict';
    var root = document.getElementById('pantry-home-root');
    if (!root) {
        return;
    }
    root.addEventListener('click', function (e) {
        var btn = e.target && e.target.closest ? e.target.closest('[data-qty-step]') : null;
        if (!btn || !root.contains(btn)) {
            return;
        }
        var delta = parseInt(btn.getAttribute('data-qty-step'), 10);
        if (!delta) {
            return;
        }
        var wrap = btn.closest('.pantry-qty-stepper');
        if (!wrap) {
            return;
        }
        var input = wrap.querySelector('input[name="quantity"]');
        if (!input) {
            return;
        }
        e.preventDefault();
        var n = parseInt(String(input.value || '').trim(), 10);
        var v = Number.isFinite(n) && n > 0 ? n : 1;
        v += delta;
        if (v < 1) {
            v = 1;
        }
        var maxLen = parseInt(input.getAttribute('maxlength'), 10) || 12;
        var maxVal = Math.pow(10, maxLen) - 1;
        if (v > maxVal) {
            v = maxVal;
        }
        input.value = String(v);
    });
}());

(function () {
    'use strict';

    var invForm = document.getElementById('pantry-inventory-bulk-form');
    var selectAll = document.getElementById('pantry-inventory-select-all');
    if (invForm && selectAll) {
        selectAll.addEventListener('change', function () {
            selectAll.indeterminate = false;
            invForm.querySelectorAll('input[name="item_id"][type="checkbox"]').forEach(function (cb) {
                cb.checked = selectAll.checked;
            });
        });
        invForm.querySelectorAll('input[name="item_id"][type="checkbox"]').forEach(function (cb) {
            cb.addEventListener('change', function () {
                var all = invForm.querySelectorAll('input[name="item_id"][type="checkbox"]');
                var on = invForm.querySelectorAll('input[name="item_id"][type="checkbox"]:checked');
                selectAll.checked = all.length > 0 && on.length === all.length;
                selectAll.indeterminate = on.length > 0 && on.length < all.length;
            });
        });
    }
}());

(function () {
    'use strict';
    var zoneRoot = document.getElementById('pantry-zone-root');
    if (!zoneRoot || !window.fetch || !window.FormData) {
        return;
    }

    function setTileInPantry(tileInner, inPantry) {
        if (!tileInner) {
            return;
        }
        if (inPantry) {
            tileInner.classList.add('pantry-ingtile--added');
            if (!tileInner.querySelector('.pantry-ingtile-added-mark')) {
                var nameEl = tileInner.querySelector('.pantry-ingtile-name');
                if (!nameEl) {
                    return;
                }
                var mark = document.createElement('span');
                mark.className = 'pantry-ingtile-added-mark';
                mark.setAttribute('title', 'In your pantry');
                mark.setAttribute('aria-hidden', 'true');
                mark.innerHTML = '<i class="bi bi-check-circle-fill"></i>';
                var badge = document.createElement('span');
                badge.className = 'pantry-ingtile-badge';
                badge.textContent = 'In pantry';
                nameEl.insertAdjacentElement('afterend', mark);
                mark.insertAdjacentElement('afterend', badge);
            }
        } else {
            tileInner.classList.remove('pantry-ingtile--added');
            tileInner.querySelectorAll('.pantry-ingtile-added-mark, .pantry-ingtile-badge').forEach(function (el) {
                el.remove();
            });
        }
    }

    function visibleCatalogItems() {
        return Array.prototype.slice
            .call(zoneRoot.querySelectorAll('[data-catalog-item]'))
            .filter(function (el) {
                return !el.classList.contains('d-none');
            });
    }

    function focusNextItemAfterAdd(currentItem) {
        var vis = visibleCatalogItems();
        var i = vis.indexOf(currentItem);
        if (i === -1 || i >= vis.length - 1) {
            return;
        }
        var next = vis[i + 1];
        next.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        var nextAdd = next.querySelector('.pantry-mini-btn--add');
        if (nextAdd) {
            window.setTimeout(function () {
                nextAdd.focus();
            }, 320);
        }
    }

    /**
     * Django's pantry_zone URL must end with a trailing slash. Some browsers expose
     * form.action without it or resolve relative actions badly, which yields HTTP 404.
     */
    function catalogQuickPostUrl(formEl) {
        var raw =
            zoneRoot.getAttribute('data-pantry-zone-post-url') ||
            formEl.getAttribute('action') ||
            '';
        if (!raw) {
            var path = window.location.pathname || '/';
            raw = path.endsWith('/') ? path : path + '/';
        }
        try {
            var u =
                raw.indexOf('http') === 0
                    ? new URL(raw)
                    : new URL(raw, window.location.origin);
            if (!u.pathname.endsWith('/')) {
                u.pathname += '/';
            }
            return u.href;
        } catch (err2) {
            return raw;
        }
    }

    function parseQtyStepperInt(raw) {
        var n = parseInt(String(raw || '').trim(), 10);
        return Number.isFinite(n) && n > 0 ? n : 1;
    }

    zoneRoot.addEventListener('click', function (e) {
        var btn = e.target && e.target.closest ? e.target.closest('[data-qty-step]') : null;
        if (!btn || !zoneRoot.contains(btn)) {
            return;
        }
        var delta = parseInt(btn.getAttribute('data-qty-step'), 10);
        if (!delta) {
            return;
        }
        var wrap = btn.closest('.pantry-qty-stepper');
        if (!wrap) {
            return;
        }
        var input = wrap.querySelector('input[name="quantity"]');
        if (!input) {
            return;
        }
        e.preventDefault();
        var v = parseQtyStepperInt(input.value) + delta;
        if (v < 1) {
            v = 1;
        }
        var maxLen = parseInt(input.getAttribute('maxlength'), 10) || 12;
        var maxVal = Math.pow(10, maxLen) - 1;
        if (v > maxVal) {
            v = maxVal;
        }
        input.value = String(v);
    });

    zoneRoot.querySelectorAll('.pantry-ingtile-actions-form').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var sub = e.submitter;
            var actionVal =
                sub && sub.getAttribute('value') ? sub.getAttribute('value') : 'quick_add';
            var itemEl = form.closest('[data-catalog-item]');
            var tileInner = form.closest('.pantry-ingtile');
            if (form.getAttribute('data-pantry-quick-busy') === '1') {
                return;
            }
            var csrfIn = form.querySelector('[name=csrfmiddlewaretoken]');
            if (!csrfIn || !csrfIn.value) {
                window.alert('This page is out of date. Refresh and try again.');
                return;
            }
            form.setAttribute('data-pantry-quick-busy', '1');
            form.querySelectorAll('button[type="submit"]').forEach(function (b) {
                b.disabled = true;
            });
            form.querySelectorAll('.pantry-qty-step-btn').forEach(function (b) {
                b.disabled = true;
            });
            // Always build from the form node only — FormData(form, submitter) is flaky in some
            // browsers and can omit `action`, which makes Django return HTML instead of JSON.
            var fd = new FormData(form);
            fd.set('action', actionVal);
            fetch(catalogQuickPostUrl(form), {
                method: 'POST',
                body: fd,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    Accept: 'application/json',
                    'X-CSRFToken': csrfIn.value,
                },
                credentials: 'same-origin',
            })
                .then(function (r) {
                    return r.text().then(function (text) {
                        var data = null;
                        if (text) {
                            try {
                                data = JSON.parse(text);
                            } catch (err) {
                                data = null;
                            }
                        }
                        return { status: r.status, data: data };
                    });
                })
                .then(function (res) {
                    if (!res.data) {
                        if (res.status === 403) {
                            window.alert(
                                'Session or security check failed. Refresh the page and try again.'
                            );
                        } else {
                            window.alert(
                                'Could not update pantry (HTTP ' +
                                    res.status +
                                    '). Refresh the page and try again.'
                            );
                        }
                        return;
                    }
                    if (!res.data.ok) {
                        window.alert(res.data.message || 'Request failed.');
                        return;
                    }
                    if (typeof res.data.in_pantry === 'boolean') {
                        setTileInPantry(tileInner, res.data.in_pantry);
                    }
                    if (actionVal === 'quick_add') {
                        focusNextItemAfterAdd(itemEl);
                    }
                })
                .catch(function () {
                    window.alert('Could not reach the server. Try again.');
                })
                .finally(function () {
                    form.removeAttribute('data-pantry-quick-busy');
                    form.querySelectorAll('button[type="submit"]').forEach(function (b) {
                        b.disabled = false;
                    });
                    form.querySelectorAll('.pantry-qty-step-btn').forEach(function (b) {
                        b.disabled = false;
                    });
                });
        });
    });
}());
