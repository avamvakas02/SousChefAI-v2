(function () {
  "use strict";

  const metrics = {
    pageToCheckoutClickRate: "pricing_cta_clicked / pricing_page_viewed",
    paidPlanSelectionMix: "cta clicks by regular, premium, year-pass",
    pricingDropoffRate: "pricing_page_viewed without checkout_start",
  };

  function trackEvent(eventName, payload) {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: eventName,
      ...payload,
    });
    document.dispatchEvent(new CustomEvent(eventName, { detail: payload }));
  }

  trackEvent("pricing_page_viewed", {
    path: window.location.pathname,
    metrics: metrics,
  });

  document.querySelectorAll(".js-plan-cta").forEach((element) => {
    element.addEventListener("click", () => {
      trackEvent("pricing_cta_clicked", {
        plan_name: element.dataset.planName || "unknown",
        plan_tier: element.dataset.planTier || "unknown",
        billing_period: element.dataset.planBilling || "unknown",
      });
    });
  });

  document.querySelectorAll(".js-checkout-form").forEach((form) => {
    form.addEventListener("submit", () => {
      trackEvent("checkout_started", {
        plan_name: form.dataset.planName || "unknown",
        plan_tier: form.dataset.planTier || "unknown",
        billing_period: form.dataset.planBilling || "unknown",
      });
    });
  });
})();
