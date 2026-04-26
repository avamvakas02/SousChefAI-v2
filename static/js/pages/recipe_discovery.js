(function () {
    'use strict';

    function initRecommendationFallbacks() {
        document.querySelectorAll('img[data-fallback-src]').forEach(function (image) {
            image.addEventListener('error', function () {
                var fallbackSrc = image.getAttribute('data-fallback-src');
                if (!fallbackSrc || image.src.indexOf(fallbackSrc) !== -1) {
                    return;
                }
                image.src = fallbackSrc;
            });
        });
    }

    function initRefreshCountdown() {
        var refreshCounter = document.querySelector('[data-rd-refresh-at]');
        if (!refreshCounter) {
            return;
        }

        var countdown = refreshCounter.querySelector('[data-rd-refresh-countdown]');
        var refreshAt = new Date(refreshCounter.dataset.rdRefreshAt);

        function updateCountdown() {
            var remainingMs = refreshAt.getTime() - Date.now();
            if (!Number.isFinite(remainingMs) || remainingMs <= 0) {
                if (countdown) {
                    countdown.textContent = 'Refreshing...';
                }
                window.setTimeout(function () {
                    window.location.reload();
                }, 1200);
                return;
            }

            var totalSeconds = Math.floor(remainingMs / 1000);
            var hours = Math.floor(totalSeconds / 3600);
            var minutes = Math.floor((totalSeconds % 3600) / 60);
            var seconds = totalSeconds % 60;
            if (countdown) {
                countdown.textContent = [hours, minutes, seconds]
                    .map(function (value) {
                        return String(value).padStart(2, '0');
                    })
                    .join(':');
            }
        }

        updateCountdown();
        window.setInterval(updateCountdown, 1000);
    }

    function initRecommendationCarousel() {
        var carousel = document.querySelector('[data-rd-carousel]');
        if (!carousel) {
            return;
        }

        function scrollCarousel(direction) {
            var firstSlide = carousel.querySelector('.rd-recommendation-slide');
            var slideWidth = firstSlide ? firstSlide.getBoundingClientRect().width : carousel.clientWidth;
            carousel.scrollBy({
                left: direction * (slideWidth + 16),
                behavior: 'smooth',
            });
        }

        var previousButton = document.querySelector('[data-rd-carousel-prev]');
        var nextButton = document.querySelector('[data-rd-carousel-next]');

        if (previousButton) {
            previousButton.addEventListener('click', function () {
                scrollCarousel(-1);
            });
        }
        if (nextButton) {
            nextButton.addEventListener('click', function () {
                scrollCarousel(1);
            });
        }
    }

    function initGenerationForms() {
        document.querySelectorAll('.rd-generation-form').forEach(function (form) {
            var button = form.querySelector('.rd-generation-btn');
            if (!button || button.disabled) {
                return;
            }

            var defaultLabel = button.querySelector('.rd-generate-default');
            var loadingLabel = button.querySelector('.rd-generate-loading');
            var submitted = false;

            form.addEventListener('submit', function () {
                if (submitted) {
                    return;
                }
                submitted = true;
                button.disabled = true;
                if (defaultLabel) {
                    defaultLabel.classList.add('d-none');
                }
                if (loadingLabel) {
                    loadingLabel.classList.remove('d-none');
                }
                button.setAttribute('aria-busy', 'true');
            });
        });
    }

    function printMissingIngredients() {
        var list = document.querySelector('#missing-ingredients-list');
        if (!list) {
            return;
        }

        var items = Array.prototype.slice
            .call(list.querySelectorAll('li'))
            .map(function (item) {
                return item.textContent.trim();
            })
            .filter(Boolean);

        if (!items.length) {
            return;
        }

        var titleNode = document.querySelector('.rd-notebook-title');
        var title = titleNode && titleNode.textContent ? titleNode.textContent.trim() : 'Recipe';
        var printable = window.open('', '_blank', 'width=720,height=900');
        if (!printable) {
            return;
        }

        var lines = items
            .map(function (item) {
                return '<li>' + item + '</li>';
            })
            .join('');

        printable.document.write(
            '<html>' +
                '<head>' +
                '<title>Missing Ingredients - ' + title + '</title>' +
                '<style>' +
                'body { font-family: Arial, sans-serif; margin: 24px; color: #2c1810; }' +
                'h1 { font-size: 22px; margin-bottom: 8px; }' +
                'p { color: #6b7280; margin-bottom: 16px; }' +
                'ul { padding-left: 20px; }' +
                'li { margin-bottom: 8px; font-size: 16px; }' +
                '</style>' +
                '</head>' +
                '<body>' +
                '<h1>Missing Ingredients</h1>' +
                '<p>' + title + '</p>' +
                '<ul>' + lines + '</ul>' +
                '</body>' +
                '</html>'
        );
        printable.document.close();
        printable.focus();
        printable.print();
    }

    function initRecipeDetailActions() {
        document.querySelectorAll('[data-action="print-missing-ingredients"]').forEach(function (button) {
            button.addEventListener('click', printMissingIngredients);
        });
    }

    function init() {
        initRecommendationFallbacks();
        initRefreshCountdown();
        initRecommendationCarousel();
        initGenerationForms();
        initRecipeDetailActions();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
}());
