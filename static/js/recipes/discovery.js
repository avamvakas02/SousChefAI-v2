(function () {
  "use strict";

  const root = document.querySelector(".recipe-discovery-page");
  if (!root) return;

  const ICONS = {
    time: root.dataset.iconTimeUrl || "/static/images/icons/rcard_time.png",
    difficulty: root.dataset.iconDifficultyUrl || "/static/images/icons/rcard_difficuty.png",
    portion: root.dataset.iconPortionUrl || "/static/images/icons/rcard_portion.png",
    pantryMatch: root.dataset.iconPantryMatchUrl || "/static/images/icons/rcard_pantry_match.png",
  };

  let latestGeneratedRecipes = [];
  let favoriteRecipeIds = new Set();
  let dailyRecipes = [];
  const DISCOVERY_RESULTS_KEY = "recipeDiscoveryResults";
  const DEFAULT_RECIPE_IMAGE = "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=900&q=80";
  const DAILY_AUTOSLIDE_MS = 4500;
  const DAILY_RESUME_AFTER_MANUAL_MS = 7000;
  const LEGACY_DAILY_RECIPE_ID = "daily_hard_parmesan_emulsion_pasta";
  const LEGACY_DAILY_RECIPE_TITLE = "parmesan emulsion pasta";
  const DAILY_REPLACEMENT_RECIPE = {
    id: "daily_hard_herb_crusted_salmon",
    title: "Herb-Crusted Salmon with Lemon Butter",
    description: "Crisp herb crusted salmon finished with a silky lemon butter glaze.",
    cook_time_minutes: 46,
    difficulty: "Hard",
    servings: 2,
    pantry_match_percent: 76,
    ingredients: ["salmon fillets", "parsley", "dill", "garlic", "butter", "lemon", "olive oil"],
    used_pantry_ingredients: ["garlic", "butter", "lemon", "olive oil"],
    missing_ingredients: ["salmon fillets", "parsley", "dill"],
    why_suggested: "A more advanced fish technique with bright, balanced flavors.",
    steps: [
      "Pat salmon dry and press a chopped herb-garlic crust onto the flesh side.",
      "Sear salmon crust-side down in olive oil until golden, then flip briefly.",
      "Add butter, baste with foaming fat, and cook to medium doneness.",
      "Deglaze pan with lemon juice, swirl into butter, and spoon over salmon.",
    ],
    macros: { calories: "590 kcal", protein: "39 g", carbs: "6 g", fat: "44 g" },
    equipment: ["Cast-iron skillet", "Fish spatula", "Small saucepan"],
    chef_tip: "Press the herb crust gently for the first 30 seconds so it adheres and browns evenly.",
    image_url: "https://images.unsplash.com/photo-1525755662778-989d0524087e?auto=format&fit=crop&w=1200&q=80",
  };

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function getCsrfToken() {
    return (document.cookie.split("; ").find((r) => r.startsWith("csrftoken=")) || "").split("=")[1] || "";
  }

  function safeUpgradeUrl(url) {
    if (typeof url !== "string") return "/pricing/";
    const trimmed = url.trim();
    if (!trimmed) return "/pricing/";
    if (trimmed.startsWith("/")) return trimmed;
    return "/pricing/";
  }

  function renderStatusMessage(statusEl, message, upgradeUrl = "") {
    if (!statusEl) return;
    const text = String(message || "").trim();
    if (!text) {
      statusEl.textContent = "";
      return;
    }
    if (upgradeUrl) {
      const href = safeUpgradeUrl(upgradeUrl);
      statusEl.innerHTML = `${escapeHtml(text)} <a href="${escapeHtml(href)}" class="btn btn-sm btn-outline-primary ms-2">Upgrade Now</a>`;
      return;
    }
    statusEl.textContent = text;
  }

  function buildRecipeId(recipe) {
    if (!recipe || typeof recipe !== "object") return "";
    const directId = recipe.id || recipe.recipe_id;
    if (directId) return String(directId);

    const title = typeof recipe.title === "string" ? recipe.title.trim() : "";
    if (!title) return "";
    return `gemini_${title.replace(/\s+/g, "_").toLowerCase()}`;
  }

  function renderRecipeCard(recipe, index) {
    const imageUrl = recipe.image_url || recipe.image || DEFAULT_RECIPE_IMAGE;
    const timeLabel = `${recipe.cook_time_minutes ?? "-"}'`;
    const difficulty = recipe.difficulty || "Easy";
    const servings = recipe.servings || "2";
    const pantryMatch = `${recipe.pantry_match_percent ?? 0}%`;
    const nutrition = recipe.nutrition_score ?? "-";
    const value = recipe.value_score ?? "-";
    const cost = recipe.cost_estimate && recipe.cost_estimate.per_serving_usd !== undefined
      ? `$${recipe.cost_estimate.per_serving_usd}/serving`
      : "N/A";

    return `
      <article class="recipe-card" data-recipe-index="${index}">
        <div class="recipe-card-image-wrap">
          <img
            class="recipe-card-image"
            src="${escapeHtml(imageUrl)}"
            alt="${escapeHtml(recipe.title)}"
            loading="lazy"
            decoding="async"
          >
          <button class="recipe-fav-btn" type="button" title="Add to Favourites" aria-label="Add to Favourites">♡</button>
        </div>
        <div class="recipe-card-body">
          <h3 class="recipe-card-title">${escapeHtml(recipe.title)}</h3>
          <p class="mb-2 small text-muted">
            Nutrition ${escapeHtml(nutrition)} | Value ${escapeHtml(value)} | ${escapeHtml(cost)}
          </p>
          <div class="recipe-meta">
            <div class="recipe-meta-item">
              <div class="recipe-meta-value">
                <img class="recipe-meta-icon" src="${escapeHtml(ICONS.time)}" alt="Time icon">
                <p>${escapeHtml(timeLabel)}</p>
              </div>
            </div>
            <div class="recipe-meta-item">
              <div class="recipe-meta-value">
                <img class="recipe-meta-icon" src="${escapeHtml(ICONS.difficulty)}" alt="Difficulty icon">
                <p>${escapeHtml(difficulty)}</p>
              </div>
            </div>
            <div class="recipe-meta-item">
              <div class="recipe-meta-value">
                <img class="recipe-meta-icon" src="${escapeHtml(ICONS.portion)}" alt="Portions icon">
                <p>${escapeHtml(servings)}</p>
              </div>
            </div>
            <div class="recipe-meta-item">
              <div class="recipe-meta-value">
                <img class="recipe-meta-icon" src="${escapeHtml(ICONS.pantryMatch)}" alt="Pantry match icon">
                <p>${escapeHtml(pantryMatch)}</p>
              </div>
            </div>
          </div>
          <button type="button" class="recipe-details-btn">Show The Details</button>
        </div>
      </article>
    `;
  }

  function renderSkeletonCards(count = 6) {
    return `
      <div class="skeleton-grid" aria-hidden="true">
        ${Array.from({ length: count })
          .map(
            () => `
          <article class="skeleton-card">
            <div class="skeleton-image skeleton-shimmer"></div>
            <div class="skeleton-body">
              <div class="skeleton-title skeleton-shimmer"></div>
              <div class="skeleton-title short skeleton-shimmer"></div>
              <div class="skeleton-meta">
                <div class="skeleton-meta-item skeleton-shimmer"></div>
                <div class="skeleton-meta-item skeleton-shimmer"></div>
                <div class="skeleton-meta-item skeleton-shimmer"></div>
                <div class="skeleton-meta-item skeleton-shimmer"></div>
              </div>
              <div class="skeleton-btn skeleton-shimmer"></div>
            </div>
          </article>
        `
          )
          .join("")}
      </div>
    `;
  }

  function revealResultsWithTransition(markup) {
    const resultsContainer = document.getElementById("resultsContainer");
    resultsContainer.innerHTML = `<div class="results-fade-enter">${markup}</div>`;
    const wrapper = resultsContainer.firstElementChild;

    if (!wrapper) return;

    requestAnimationFrame(() => {
      wrapper.classList.add("results-fade-enter-active");
    });
  }

  function attachImageFallbacks(container) {
    if (!container) return;
    container.querySelectorAll(".recipe-card-image").forEach((image) => {
      image.addEventListener("error", () => {
        if (image.dataset.fallbackApplied === "true") return;
        image.dataset.fallbackApplied = "true";
        image.src = DEFAULT_RECIPE_IMAGE;
      });
    });
  }

  function renderRecipes(data) {
    const status = document.getElementById("statusMessage");
    const resultsContainer = document.getElementById("resultsContainer");

    if (!data.recipes || data.recipes.length === 0) {
      const upgradeUrl = data?.meta?.upgrade_url || "";
      renderStatusMessage(status, data.fallback_message || "No recipes found.", upgradeUrl);
      resultsContainer.innerHTML = "";
      return;
    }

    renderStatusMessage(status, "");
    latestGeneratedRecipes = data.recipes;
    sessionStorage.setItem(DISCOVERY_RESULTS_KEY, JSON.stringify(data));
    revealResultsWithTransition(
      `<div class="recipe-grid">${data.recipes.map((r, i) => renderRecipeCard(r, i)).join("")}</div>`
    );
    attachImageFallbacks(resultsContainer);
    bindCardClicks(resultsContainer, latestGeneratedRecipes);
    refreshFavoriteStates(resultsContainer, latestGeneratedRecipes);
  }

  function restoreRecipesFromSession() {
    const status = document.getElementById("statusMessage");
    try {
      const raw = sessionStorage.getItem(DISCOVERY_RESULTS_KEY);
      if (!raw) return;
      const savedData = JSON.parse(raw);
      if (!savedData || !Array.isArray(savedData.recipes) || savedData.recipes.length === 0) return;
      renderRecipes(savedData);
      renderStatusMessage(status, "");
    } catch (_err) {
      sessionStorage.removeItem(DISCOVERY_RESULTS_KEY);
    }
  }

  function bindCardClicks(container, recipes) {
    if (!container || !Array.isArray(recipes)) return;

    container.querySelectorAll(".recipe-card").forEach((card) => {
      card.addEventListener("click", () => {
        const index = Number(card.getAttribute("data-recipe-index"));
        const recipe = recipes[index];
        if (recipe) {
          const detailsButton = card.querySelector(".recipe-details-btn");
          openRecipeDetails(recipe, detailsButton);
        }
      });

      const detailsButton = card.querySelector(".recipe-details-btn");
      if (detailsButton) {
        detailsButton.addEventListener("click", (event) => {
          event.stopPropagation();
          const index = Number(card.getAttribute("data-recipe-index"));
          const recipe = recipes[index];
          if (recipe) openRecipeDetails(recipe, detailsButton);
        });
      }

      const favButton = card.querySelector(".recipe-fav-btn");
      if (favButton) {
        favButton.addEventListener("click", async (event) => {
          event.stopPropagation();
          const index = Number(card.getAttribute("data-recipe-index"));
          const recipe = recipes[index];
          if (!recipe) return;
          await addRecipeToFavorites(recipe, favButton);
        });
      }
    });
  }

  function setFavoriteButtonState(button, isFavorite) {
    if (!button) return;
    button.classList.toggle("is-favorite", isFavorite);
    button.textContent = isFavorite ? "♥" : "♡";
    button.title = "Add to Favourites";
    button.setAttribute("aria-label", "Add to Favourites");
  }

  async function refreshFavoriteStates(container, recipes) {
    if (!container || !Array.isArray(recipes)) return;
    const cards = container.querySelectorAll(".recipe-card");
    const checks = Array.from(cards).map(async (card) => {
      const index = Number(card.getAttribute("data-recipe-index"));
      const recipe = recipes[index];
      const recipeId = buildRecipeId(recipe);
      if (!recipeId) return;

      const favButton = card.querySelector(".recipe-fav-btn");
      try {
        const response = await fetch(`/recipes/favorite/status/?recipe_id=${encodeURIComponent(recipeId)}`);
        if (!response.ok) return;
        const data = await response.json();
        const isFavorite = data.is_favorite === true;
        if (isFavorite) {
          favoriteRecipeIds.add(recipeId);
        } else {
          favoriteRecipeIds.delete(recipeId);
        }
        setFavoriteButtonState(favButton, isFavorite);
      } catch (_err) {
        // Keep discovery cards interactive even if status checks fail.
      }
    });

    await Promise.all(checks);
  }

  function readDailyRecipes() {
    const raw = document.getElementById("daily-recipes-data");
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw.textContent || "[]");
      if (!Array.isArray(parsed)) return [];
      return parsed.map((recipe) => {
        const recipeId = String(recipe && recipe.id ? recipe.id : "").trim().toLowerCase();
        const recipeTitle = String(recipe && recipe.title ? recipe.title : "").trim().toLowerCase();
        if (recipeId === LEGACY_DAILY_RECIPE_ID || recipeTitle === LEGACY_DAILY_RECIPE_TITLE) {
          return { ...DAILY_REPLACEMENT_RECIPE };
        }
        return recipe;
      });
    } catch (_err) {
      return [];
    }
  }

  function setupDailyCarousel(viewport, previousButton, nextButton) {
    if (!viewport || !previousButton || !nextButton) return;
    if (viewport.dataset.carouselInitialized === "true") return;
    viewport.dataset.carouselInitialized = "true";

    let autoSlideTimer = null;
    let resumeTimer = null;
    let isPaused = false;

    const cardStepWidth = () => {
      const firstCard = viewport.querySelector(".recipe-card");
      if (!firstCard) return viewport.clientWidth || 1;
      const track = viewport.querySelector(".daily-carousel-track");
      const gap = track ? parseFloat(getComputedStyle(track).gap || "0") : 0;
      return Math.max(1, Math.round(firstCard.getBoundingClientRect().width + gap));
    };

    const clearTimers = () => {
      if (autoSlideTimer) {
        clearInterval(autoSlideTimer);
        autoSlideTimer = null;
      }
      if (resumeTimer) {
        clearTimeout(resumeTimer);
        resumeTimer = null;
      }
    };

    const pauseAutoSlide = () => {
      isPaused = true;
      clearTimers();
    };

    const scrollOneStep = (direction, smooth) => {
      const maxLeft = Math.max(0, viewport.scrollWidth - viewport.clientWidth);
      if (maxLeft <= 0) return;

      const step = cardStepWidth() * direction;
      let targetLeft = viewport.scrollLeft + step;

      if (direction > 0 && targetLeft > maxLeft - 1) {
        targetLeft = 0;
      } else if (direction < 0 && targetLeft < 1) {
        targetLeft = maxLeft;
      }

      viewport.scrollTo({
        left: targetLeft,
        behavior: smooth ? "smooth" : "auto",
      });
    };

    const startAutoSlide = () => {
      if (isPaused) return;
      clearTimers();
      autoSlideTimer = setInterval(() => {
        if (document.hidden || viewport.matches(":hover")) return;
        scrollOneStep(1, true);
      }, DAILY_AUTOSLIDE_MS);
    };

    const scheduleResumeAfterManual = () => {
      clearTimers();
      isPaused = false;
      resumeTimer = setTimeout(() => {
        startAutoSlide();
      }, DAILY_RESUME_AFTER_MANUAL_MS);
    };

    const scrollByViewport = (direction) => {
      scrollOneStep(direction, true);
      scheduleResumeAfterManual();
    };

    previousButton.addEventListener("click", () => scrollByViewport(-1));
    nextButton.addEventListener("click", () => scrollByViewport(1));

    viewport.addEventListener("mouseenter", pauseAutoSlide);
    viewport.addEventListener("mouseleave", () => {
      isPaused = false;
      startAutoSlide();
    });
    viewport.addEventListener("focusin", pauseAutoSlide);
    viewport.addEventListener("focusout", () => {
      isPaused = false;
      startAutoSlide();
    });
    viewport.addEventListener("touchstart", pauseAutoSlide, { passive: true });
    viewport.addEventListener(
      "touchend",
      () => {
        isPaused = false;
        startAutoSlide();
      },
      { passive: true }
    );

    document.addEventListener("visibilitychange", () => {
      if (document.hidden) {
        pauseAutoSlide();
        return;
      }
      isPaused = false;
      startAutoSlide();
    });

    startAutoSlide();
  }

  function renderDailySuggestions() {
    const track = document.getElementById("dailyCarouselTrack");
    const viewport = document.getElementById("dailyCarouselViewport");
    const previousButton = document.getElementById("dailyCarouselPrev");
    const nextButton = document.getElementById("dailyCarouselNext");
    if (!track || !viewport || !previousButton || !nextButton) return;

    dailyRecipes = readDailyRecipes();
    if (!dailyRecipes.length) {
      track.innerHTML = "";
      previousButton.disabled = true;
      nextButton.disabled = true;
      return;
    }

    track.innerHTML = dailyRecipes.map((recipe, index) => renderRecipeCard(recipe, index)).join("");
    attachImageFallbacks(track);
    bindCardClicks(track, dailyRecipes);
    refreshFavoriteStates(track, dailyRecipes);
    setupDailyCarousel(viewport, previousButton, nextButton);
  }

  async function addRecipeToFavorites(recipe, button) {
    const recipeId = buildRecipeId(recipe);
    if (!recipeId) return;

    if (favoriteRecipeIds.has(recipeId)) {
      setFavoriteButtonState(button, true);
      return;
    }

    button.disabled = true;
    try {
      const csrfToken = getCsrfToken();
      const response = await fetch("/recipes/favorite/toggle/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          recipe_id: recipeId,
          action: "add",
          recipe_data: recipe,
        }),
      });

      if (!response.ok) return;
      favoriteRecipeIds.add(recipeId);
      setFavoriteButtonState(button, true);
    } catch (_err) {
      // Ignore network errors so recipe detail flow remains unaffected.
    } finally {
      button.disabled = false;
    }
  }

  function openRecipeDetails(recipe) {
    if (!recipe) return;
    sessionStorage.setItem("selectedRecipe", JSON.stringify(recipe));
    window.location.href = "/recipes/discover/detail/";
  }

  async function generateRecipes() {
    const status = document.getElementById("statusMessage");
    const resultsContainer = document.getElementById("resultsContainer");
    status.textContent = "Generating recipes...";
    resultsContainer.innerHTML = renderSkeletonCards();

    try {
      const response = await fetch("/recipes/discover/api/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify({
          extra_items: ["tomato"],
          goal: "quick",
          dietary_constraints: {},
          preferences: { servings: 2 },
          pantry_only: false,
          max_missing: 2,
        }),
      });

      const raw = await response.text();
      let data;
      try {
        data = JSON.parse(raw);
      } catch (_err) {
        renderStatusMessage(status, `Request failed (${response.status}). Response was not JSON.`);
        return;
      }

      if (response.status === 402) {
        const message =
          data.fallback_message ||
          (Array.isArray(data.errors) && data.errors[0]) ||
          "You have reached your monthly limit.";
        const upgradeUrl = data?.meta?.upgrade_url || "/pricing/";
        renderStatusMessage(status, message, upgradeUrl);
        resultsContainer.innerHTML = "";
        return;
      }

      renderRecipes(data);
    } catch (error) {
      renderStatusMessage(status, `Request error: ${error.message}`);
    }
  }

  const generateBtn = document.getElementById("generateBtn");
  renderDailySuggestions();
  if (generateBtn) {
    generateBtn.addEventListener("click", generateRecipes);
  }
  restoreRecipesFromSession();

  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get("auto_generate") === "true") {
    const newUrl = `${window.location.protocol}//${window.location.host}${window.location.pathname}`;
    window.history.replaceState({ path: newUrl }, "", newUrl);
    sessionStorage.removeItem(DISCOVERY_RESULTS_KEY);
    setTimeout(generateRecipes, 100);
  }
})();
