(function () {
  "use strict";

  const profileRoot = document.querySelector("[data-recipe-detail-url]");
  if (!profileRoot) return;
  const recipeDetailUrl = profileRoot.dataset.recipeDetailUrl || "/recipes/discover/detail/";

  function buildRecipeId(recipeData) {
    if (!recipeData || typeof recipeData !== "object") return "";
    const directId = recipeData.id || recipeData.recipe_id;
    if (directId) return String(directId);

    const title = typeof recipeData.title === "string" ? recipeData.title.trim() : "";
    if (!title) return "";
    return `gemini_${title.replace(/\s+/g, "_").toLowerCase()}`;
  }

  async function addFavoriteFromCard(scriptId, buttonElement) {
    try {
      const dataElement = document.getElementById(scriptId);
      if (!dataElement) return;
      const recipeData = JSON.parse(dataElement.textContent);
      const recipeId = buildRecipeId(recipeData);
      if (!recipeId) return;

      if (buttonElement) buttonElement.disabled = true;
      const csrfToken = (document.cookie.split("; ").find((r) => r.startsWith("csrftoken=")) || "").split("=")[1] || "";
      await fetch("/recipes/favorite/toggle/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify({
          recipe_id: recipeId,
          action: "add",
          recipe_data: recipeData,
        }),
      });
    } catch (e) {
      console.error("Failed to add favorite", e);
    } finally {
      if (buttonElement) buttonElement.disabled = false;
    }
  }

  function loadFavorite(scriptId) {
    try {
      const dataElement = document.getElementById(scriptId);
      if (!dataElement) return;
      const recipeData = JSON.parse(dataElement.textContent);
      sessionStorage.setItem("selectedRecipe", JSON.stringify(recipeData));
      window.location.href = recipeDetailUrl;
    } catch (e) {
      console.error("Failed to load recipe", e);
    }
  }

  function handleFavoriteCardKeydown(event, scriptId) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      loadFavorite(scriptId);
    }
  }

  window.addFavoriteFromCard = addFavoriteFromCard;
  window.loadFavorite = loadFavorite;
  window.handleFavoriteCardKeydown = handleFavoriteCardKeydown;
})();
