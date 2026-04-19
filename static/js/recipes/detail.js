(function () {
  "use strict";

  const pageRoot = document.querySelector(".recipe-detail-page");
  if (!pageRoot) return;

  const discoveryUrl = pageRoot.dataset.discoveryUrl || "/recipes/discover/";
  const chatHistories = {};
  let recipe = null;
  let isFavorited = false;

  function escapeHtml(value) {
    return String(value || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  function readRecipeFromSession() {
    try {
      return JSON.parse(sessionStorage.getItem("selectedRecipe") || "null");
    } catch (_err) {
      return null;
    }
  }

  function buildRecipeId(recipeData) {
    if (!recipeData || typeof recipeData !== "object") return "";
    const directId = recipeData.id || recipeData.recipe_id;
    if (directId) return String(directId);

    const title = typeof recipeData.title === "string" ? recipeData.title.trim() : "";
    if (!title) return "";
    return `gemini_${title.replace(/\s+/g, "_").toLowerCase()}`;
  }

  function toggleStepCompletion(card) {
    card.classList.toggle("completed");
  }

  function getCsrfToken() {
    return (document.cookie.split("; ").find((r) => r.startsWith("csrftoken=")) || "").split("=")[1] || "";
  }

  function renderRecipeDetails(recipeData) {
    const imageUrl =
      recipeData.image_url ||
      recipeData.image ||
      "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=1200&q=80";
    const steps = Array.isArray(recipeData.steps) ? recipeData.steps : [];
    const usedPantry = Array.isArray(recipeData.used_pantry_ingredients) ? recipeData.used_pantry_ingredients : [];
    const missingIngredients = Array.isArray(recipeData.missing_ingredients) ? recipeData.missing_ingredients : [];

    document.getElementById("recipeDetailImage").src = imageUrl;
    document.getElementById("recipeDetailTitle").textContent = recipeData.title || "Recipe details";
    document.getElementById("recipeDetailDescription").textContent = recipeData.description || "No description available.";
    document.getElementById("recipeDetailTime").textContent = `${recipeData.cook_time_minutes ?? "-"}'`;
    document.getElementById("recipeDetailDifficulty").textContent = recipeData.difficulty || "Easy";
    document.getElementById("recipeDetailServings").textContent = recipeData.servings || "2";
    document.getElementById("recipeDetailMatch").textContent = `${recipeData.pantry_match_percent ?? 0}%`;
    document.getElementById("recipeDetailUsed").textContent = usedPantry.join(", ") || "None";
    document.getElementById("recipeDetailMissing").textContent = missingIngredients.join(", ") || "None";
    document.getElementById("recipeDetailWhy").textContent = recipeData.why_suggested || "Suggested based on your pantry.";

    const macros = recipeData.macros || {};
    if (Object.keys(macros).length > 0) {
      document.getElementById("recipeDetailMacrosContainer").classList.remove("d-none");
      let macrosHTML = "";
      for (const [key, val] of Object.entries(macros)) {
        if (val) {
          macrosHTML += `
            <div class="macro-card">
              <span class="macro-label">${escapeHtml(key)}</span>
              <span class="macro-value">${escapeHtml(val)}</span>
            </div>`;
        }
      }
      document.getElementById("recipeDetailMacros").innerHTML = macrosHTML;
    }

    const equipment = recipeData.equipment || [];
    if (equipment.length > 0) {
      document.getElementById("recipeDetailEquipmentContainer").classList.remove("d-none");
      document.getElementById("recipeDetailEquipment").innerHTML = equipment
        .map((eq) => `<li class="equipment-tag">${escapeHtml(eq)}</li>`)
        .join("");
    }

    if (recipeData.chef_tip) {
      document.getElementById("recipeDetailChefTipContainer").classList.remove("d-none");
      document.getElementById("recipeDetailChefTip").textContent = recipeData.chef_tip;
    }

    document.getElementById("recipeDetailSteps").innerHTML = steps.length
      ? steps
          .map(
            (step, idx) => `
          <div class="step-card" onclick="toggleStepCompletion(this)">
            <div class="step-checkbox">
              <svg width="14" height="10" viewBox="0 0 14 10" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M1 5L5 9L13 1" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
               </svg>
            </div>
            <div class="step-content">
              <span class="step-number">Step ${idx + 1}</span>
              <p class="step-text">${escapeHtml(step)}</p>
              <button class="btn btn-sm btn-outline-secondary mt-2 ask-souschef-btn" onclick="toggleAskSouschef(event, ${idx})">
                 <i class="bi bi-chat-dots me-1"></i> Ask SousChef
              </button>
              <div class="ask-souschef-panel d-none" id="askPanel_${idx}" onclick="event.stopPropagation()">
                 <div class="chat-history mb-2" id="chatHistory_${idx}"></div>
                 <div class="input-group input-group-sm">
                    <input type="text" class="form-control" id="askInput_${idx}" placeholder="Ask a question about this step..." onkeydown="handleAskEnter(event, ${idx})">
                    <button class="btn btn-secondary" onclick="submitAsk(${idx})">Send</button>
                 </div>
                 <div class="text-danger small mt-1 d-none" id="askError_${idx}"></div>
              </div>
            </div>
          </div>
        `
          )
          .join("")
      : "<div class='text-muted'>No steps provided.</div>";

  }

  function toggleAskSouschef(event, idx) {
    event.stopPropagation();
    const panel = document.getElementById(`askPanel_${idx}`);
    panel.classList.toggle("d-none");
  }

  function handleAskEnter(event, idx) {
    if (event.key === "Enter") {
      submitAsk(idx);
    }
  }

  async function submitAsk(idx) {
    const inputField = document.getElementById(`askInput_${idx}`);
    const question = inputField.value.trim();
    if (!question || !recipe) return;

    inputField.value = "";
    inputField.disabled = true;

    if (!chatHistories[idx]) chatHistories[idx] = [];
    const history = chatHistories[idx];

    history.push({ role: "user", text: question });
    renderChatHistory(idx);

    const errorDiv = document.getElementById(`askError_${idx}`);
    errorDiv.classList.add("d-none");

    try {
      const csrfToken = getCsrfToken();
      const stepText = Array.isArray(recipe.steps) ? recipe.steps[idx] || "" : "";
      const ingredients = Array.isArray(recipe.used_pantry_ingredients)
        ? recipe.used_pantry_ingredients
        : Array.isArray(recipe.ingredients)
          ? recipe.ingredients
          : [];

      const historyToSend = history.slice(0, -1);

      const response = await fetch("/recipes/discover/ask/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          question: question,
          recipe_title: recipe.title,
          ingredients: ingredients,
          step_text: stepText,
          history: historyToSend,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Failed to ask SousChef.");
      }

      history.push({ role: "model", text: data.answer });
      renderChatHistory(idx);
    } catch (err) {
      errorDiv.textContent = err.message;
      errorDiv.classList.remove("d-none");
    } finally {
      inputField.disabled = false;
      inputField.focus();
    }
  }

  function renderChatHistory(idx) {
    const history = chatHistories[idx] || [];
    const container = document.getElementById(`chatHistory_${idx}`);
    if (!container) return;

    if (history.length === 0) {
      container.innerHTML = "";
      return;
    }

    container.innerHTML = history
      .map((msg) => {
        const isUser = msg.role === "user";
        return `
          <div class="chat-msg ${isUser ? "chat-msg-user" : "chat-msg-bot"}">
             <div class="chat-bubble ${isUser ? "chat-bubble-user" : "chat-bubble-bot"}">
                ${escapeHtml(msg.text)}
             </div>
          </div>
       `;
      })
      .join("");
    container.scrollTop = container.scrollHeight;
  }

  async function checkFavoriteStatus(recipeId) {
    try {
      const response = await fetch(`/recipes/favorite/status/?recipe_id=${encodeURIComponent(recipeId)}`);
      if (!response.ok) return;
      const data = await response.json();
      isFavorited = data.is_favorite === true;
      renderFavoriteIcon();
    } catch (e) {
      console.error(e);
    }
  }

  async function toggleFavoriteState() {
    if (!recipe) return;
    const recipeId = buildRecipeId(recipe);
    if (!recipeId) return;
    const action = isFavorited ? "remove" : "add";
    const csrfToken = getCsrfToken();

    const btn = document.getElementById("favoriteBtn");
    if (!btn) return;
    btn.disabled = true;

    try {
      const response = await fetch("/recipes/favorite/toggle/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          recipe_id: recipeId,
          action: action,
          recipe_data: recipe,
        }),
      });

      if (response.ok) {
        isFavorited = !isFavorited;
        renderFavoriteIcon();
      }
    } catch (e) {
      console.error("Failed to toggle favorite:", e);
    } finally {
      btn.disabled = false;
    }
  }

  function renderFavoriteIcon() {
    const icon = document.getElementById("favoriteIcon");
    const btn = document.getElementById("favoriteBtn");
    if (!icon || !btn) return;

    if (isFavorited) {
      icon.classList.remove("bi-heart");
      icon.classList.add("bi-heart-fill");
      btn.classList.add("is-favorite");
    } else {
      icon.classList.add("bi-heart");
      icon.classList.remove("bi-heart-fill");
      btn.classList.remove("is-favorite");
    }
  }

  const backLink = document.getElementById("backToDiscoveryLink");
  if (backLink) {
    backLink.addEventListener("click", (event) => {
      if (window.history.length > 1) {
        event.preventDefault();
        window.history.back();
      }
    });
  }

  recipe = readRecipeFromSession();
  if (!recipe) {
    window.location.href = discoveryUrl;
  } else {
    renderRecipeDetails(recipe);
    const recipeId = buildRecipeId(recipe);
    if (recipeId) {
      checkFavoriteStatus(recipeId);
    } else {
      const favoriteBtn = document.getElementById("favoriteBtn");
      if (favoriteBtn) favoriteBtn.classList.add("d-none");
    }
  }

  window.toggleStepCompletion = toggleStepCompletion;
  window.toggleAskSouschef = toggleAskSouschef;
  window.handleAskEnter = handleAskEnter;
  window.submitAsk = submitAsk;
  window.toggleFavoriteState = toggleFavoriteState;
})();
