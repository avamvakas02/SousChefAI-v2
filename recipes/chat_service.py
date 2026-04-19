import os
import django
from django.conf import settings
import google.generativeai as genai

def ask_souschef_chatbot(recipe_title: str, ingredients: list, step_text: str, question: str, chat_history: list = None) -> str:
    # Try getting key from settings, then env
    api_key = getattr(settings, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set.")

    genai.configure(api_key=api_key)
    # Match the model used in discovery_service
    model_name = os.getenv("GEMINI_RECIPE_MODEL", "gemini-2.5-flash")
    model = genai.GenerativeModel(model_name)

    if chat_history is None:
        chat_history = []

    formatted_history = ""
    if chat_history:
        formatted_history = "Previous Conversation:\n"
        for msg in chat_history:
            role = msg.get("role", "user")
            text = msg.get("text", "")
            formatted_history += f"{role.capitalize()}: {text}\n"

    prompt = f"""
You are the interactive Sous-Chef for a user cooking a recipe. Be helpful, concise, and speak like a friendly professional cook. 
Provide your response in plain text (no markdown formatting). Keep it strictly under 3-4 sentences.

Current Recipe: {recipe_title}
Ingredients Used: {', '.join(ingredients) if ingredients else 'Not specified.'}

The user is currently focusing on this specific step:
"{step_text}"

{formatted_history}

User Question: {question}

Sous-Chef Response:
"""

    try:
        response = model.generate_content(prompt)
        try:
            raw_text = (response.text or "").strip()
        except ValueError:
            parts = []
            for cand in getattr(response, "candidates", []) or []:
                finish = getattr(getattr(cand, "finish_reason", None), "name", None) or str(
                    getattr(cand, "finish_reason", "")
                )
                parts.append(f"blocked ({finish})")
            raw_text = "I'm sorry, I can't answer that. " + ("; ".join(parts) if parts else "Response blocked.")
        return raw_text
    except Exception as e:
        print(f"Chatbot generation error: {e}")
        return f"I'm having trouble answering right now. Error: {str(e)}"
