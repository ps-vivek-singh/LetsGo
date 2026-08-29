"""Meals & Recipe FastMCP Tool — generates dynamic, LLM-powered recipes for breakfast, lunch, and dinner."""
from __future__ import annotations

import json
import logging
import random
import re
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from services.llm_client import LLMClient

logger = logging.getLogger("commute_commander.recipe_tools")

mcp = FastMCP("recipe-server")

# ── Dynamic Generative Chef Engine (Deterministic Fallback) ───────────────────
_HEURISTIC_DISH_STYLES = {
    "breakfast": [
        ("Fluffy Herb & {ing} Omelette", 10, "Breakfast", [
            "Whisk eggs with a pinch of sea salt, black pepper, and fresh herbs in a bowl.",
            "Heat butter or olive oil in a non-stick pan over medium heat.",
            "Add {ing} and sauté for 1–2 minutes until fragrant.",
            "Pour in whisked eggs, gently lifting the edges to let uncooked egg flow underneath.",
            "Fold in half and slide onto a plate. Serve warm with toast.",
        ], "High Protein · Fast Prep", "Cook on low heat to keep eggs tender and custard-like."),
        ("Golden {ing} Breakfast Hash Skillet", 12, "Breakfast", [
            "Dice {ing} and any accompaniments into uniform bite-sized cubes.",
            "Sear in a hot skillet with olive oil until golden and crispy.",
            "Season with smoked paprika, sea salt, and freshly cracked pepper.",
            "Create a small well in the center and let everything finish crisping.",
            "Garnish with chopped scallions and enjoy hot from the skillet.",
        ], "Energizing Carbohydrates & Healthy Fats", "Do not crowd the skillet for maximum crispiness."),
        ("Creamy {ing} Power Morning Bowl", 8, "Breakfast", [
            "Warm and prepare {ing} with a splash of milk, almond milk, or olive oil.",
            "Gently fold in your choice of nuts, seeds, or fresh herbs.",
            "Season lightly to balance sweet or savory notes.",
            "Transfer to a bowl and top with a light drizzle of honey or chili oil.",
        ], "Rich in Fiber & Micronutrients", "Toast any nuts or spices beforehand to maximize depth of flavor."),
    ],
    "lunch": [
        ("Crispy Pan-Seared {ing} & Greens Warm Salad", 15, "Lunch", [
            "Season {ing} generously with salt, pepper, garlic powder, and a touch of lemon zest.",
            "Sear in a preheated skillet with olive oil for 3–5 minutes per side until caramelized.",
            "Toss crisp salad greens or grain base with lemon juice, extra virgin olive oil, and sea salt.",
            "Slice {ing} and arrange over the greens.",
            "Drizzle with pan reduction and serve immediately.",
        ], "Lean Protein · Low Carb · Fresh", "Rest protein for 3 minutes before slicing to retain juices."),
        ("Artisan {ing} & Melted Herb Ciabatta Toast", 12, "Lunch", [
            "Toast artisan bread slices in olive oil or butter until golden brown.",
            "Sauté {ing} in a hot pan with minced garlic and a pinch of chili flakes.",
            "Layer warm {ing} onto the toasted bread.",
            "Top with a light layer of cheese or microgreens and a drizzle of balsamic glaze.",
            "Slice diagonally and serve warm.",
        ], "Satisfying Comfort Lunch", "Rub raw garlic over warm toasted bread for an intense aromatic base."),
        ("Zesty {ing} & Cilantro Lime Rice Bowl", 15, "Lunch", [
            "Prepare or reheat steamed rice tossed with fresh lime juice, sea salt, and cilantro.",
            "Quickly sauté {ing} over high heat with cumin, smoked paprika, and diced onions.",
            "Assemble bowl with rice base, warm {ing}, and sliced avocado or cucumber.",
            "Finish with a spoonful of Greek yogurt or salsa.",
        ], "Balanced Macro Power Bowl", "Cook {ing} on high heat for a smoky char exterior."),
    ],
    "dinner": [
        ("Garlic Butter Basted {ing} with Charred Veggies", 20, "Dinner", [
            "Season {ing} with kosher salt, cracked black pepper, and dried thyme or rosemary.",
            "Heat a cast iron skillet over medium-high heat with a splash of high-heat oil.",
            "Sear {ing} until deep golden crust forms, then add 2 tbsp butter, smashed garlic, and fresh herbs.",
            "Baste {ing} continuously with the foaming herb butter for 2–3 minutes.",
            "Plate alongside charred seasonal greens or roasted potatoes.",
        ], "Restaurant-Quality Dinner · Gourmet", "Baste continuously in the final minutes to infuse rich aromatics."),
        ("Rustic Mediterranean {ing} & Tomato Skillet", 20, "Dinner", [
            "Heat olive oil in a skillet and gently soften sliced onions and minced garlic.",
            "Add crushed tomatoes, oregano, a pinch of red pepper flakes, and simmer into a rich sauce.",
            "Nestle {ing} into the bubbling sauce and cover over medium-low heat.",
            "Cook until {ing} is tender, succulent, and infused with sauce flavors.",
            "Garnish with crumbled feta or fresh basil and serve with crusty bread.",
        ], "Heart-Healthy Mediterranean", "Let the sauce simmer for at least 5 minutes before adding {ing}."),
        ("Fragrant Ginger Scallion {ing} Stir-Fry", 15, "Dinner", [
            "Slice {ing} into thin, bite-sized strips for even cooking.",
            "Heat sesame oil in a wok or skillet over high heat until shimmering.",
            "Flash-fry minced ginger, garlic, and scallion whites for 30 seconds until fragrant.",
            "Toss in {ing} and stir-fry vigorously for 3–4 minutes.",
            "Deglaze with a splash of soy sauce, rice vinegar, and a pinch of pepper.",
            "Serve steaming over jasmine rice or noodles.",
        ], "High Protein · Fast Wok Cooking", "Keep wok extremely hot and cook in batches if necessary."),
    ],
    "snack": [
        ("Crispy Spiced {ing} Bites", 10, "Snack", [
            "Toss {ing} lightly with olive oil, smoked paprika, sea salt, and garlic powder.",
            "Toast in a skillet or air fryer at 190°C for 6–8 minutes until crisp and golden.",
            "Cool for 2 minutes on paper towels to achieve maximum crunch.",
            "Serve as a nutritious, savory snack.",
        ], "Quick Energy · Healthy Snack", "Ensure ingredients are dry before cooking for the crispiest texture."),
    ],
}


def _clean_json_str(content: str) -> str:
    """Clean markdown code fences and extract valid JSON substring."""
    clean = content.strip()
    if "```" in clean:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean, re.IGNORECASE)
        if match:
            clean = match.group(1).strip()
        else:
            clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$", "", clean)
            clean = clean.strip()
    return clean


def _generate_heuristic_recipe(
    ingredients: List[str],
    time_constraint: str,
    meal_type: str = "meal",
) -> Dict[str, Any]:
    """Generates a dynamic, non-repeating recipe when offline or LLM unavailable."""
    m_type = meal_type.lower() if meal_type else "meal"
    if m_type not in _HEURISTIC_DISH_STYLES:
        # Default based on typical time of day or general options
        m_type = "breakfast" if "breakfast" in m_type else ("lunch" if "lunch" in m_type else "dinner")

    options = _HEURISTIC_DISH_STYLES.get(m_type, _HEURISTIC_DISH_STYLES["dinner"])
    template, base_prep, category, raw_steps, nutrition, tip = random.choice(options)

    primary_ing = ingredients[0].capitalize() if ingredients else "Eggs"
    ing_name_str = ", ".join(ingredients) if ingredients else "Fresh ingredients"
    recipe_name = template.format(ing=primary_ing)

    steps = [s.format(ing=primary_ing) for s in raw_steps]

    pantry = ["Extra virgin olive oil", "Sea salt & black pepper", "Garlic cloves", "Fresh herbs"]
    formatted_ings = [f"Fresh {i}" for i in ingredients] if ingredients else ["2 Farm eggs", "1 slice sourdough"]

    return {
        "name": recipe_name,
        "recipe_name": recipe_name,
        "meal_type": m_type,
        "time": time_constraint or f"{base_prep} min",
        "prep_time_minutes": base_prep,
        "cook_time_minutes": base_prep,
        "total_time_minutes": base_prep * 2,
        "ingredients": formatted_ings,
        "ingredients_used": formatted_ings,
        "pantry_staples": pantry,
        "steps": steps,
        "nutrition_highlights": nutrition,
        "chef_tip": tip,
        "category": f"{category} ({primary_ing})",
        "area": "Chef's Kitchen",
        "thumbnail": "",
    }


@mcp.tool(
    name="get_meal_recipe",
    description="Generate a creative, personalized recipe for breakfast, lunch, dinner, or snacks strictly utilizing user ingredients with minimal pantry extras.",
)
def get_meal_recipe(
    ingredients: Optional[List[str]] = None,
    time_constraint: str = "15 min",
    meal_type: str = "meal",
    cuisine_pref: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates an authentic, dynamic recipe via LLM or chef engine."""
    if not ingredients:
        ingredients = ["eggs"]

    meal_type_clean = (meal_type or "meal").strip().lower()
    if meal_type_clean not in ("breakfast", "lunch", "dinner", "snack", "brunch"):
        meal_type_clean = "meal"

    llm = LLMClient()
    if llm.is_available():
        try:
            prompt = (
                f"You are a Michelin-caliber chef and nutritionist. Design a distinct, creative, and delicious {meal_type_clean.upper()} recipe.\n\n"
                f"User Requested Ingredients: {', '.join(ingredients)}\n"
                f"Time Limit: {time_constraint}\n"
                f"Cuisine Preference: {cuisine_pref or 'Chef specialty'}\n\n"
                f"STRICT REQUIREMENTS:\n"
                f"1. The dish MUST prominently feature the user's ingredients: {', '.join(ingredients)}.\n"
                f"2. Add MINIMAL extra ingredients — only standard pantry essentials (e.g. olive oil, butter, salt, black pepper, garlic, onion, water, lemon).\n"
                f"3. Generate a creative, unique dish name and clear, actionable step-by-step cooking steps.\n"
                f"4. Provide realistic prep/cook time in minutes matching the time constraint.\n\n"
                f"Output MUST be pure valid JSON with this exact schema:\n"
                f"{{\n"
                f'  "name": "Creative Recipe Name",\n'
                f'  "meal_type": "{meal_type_clean}",\n'
                f'  "prep_time_minutes": 10,\n'
                f'  "cook_time_minutes": 10,\n'
                f'  "ingredients": ["2 eggs", "1 cup chopped spinach"],\n'
                f'  "pantry_staples": ["1 tbsp olive oil", "pinch of sea salt", "black pepper"],\n'
                f'  "steps": ["Step 1 description", "Step 2 description", "Step 3 description", "Step 4 description"],\n'
                f'  "nutrition_highlights": "High protein · Low carb",\n'
                f'  "chef_tip": "Pro cooking tip for best flavor or texture",\n'
                f'  "category": "Quick {meal_type_clean.capitalize()}",\n'
                f'  "area": "Mediterranean"\n'
                f"}}"
            )
            response = llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional chef. You MUST reply with valid JSON only. Do not include markdown codeblocks or conversational text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.75,
            )
            raw_text = response["choices"][0]["message"]["content"].strip()
            clean_text = _clean_json_str(raw_text)

            try:
                parsed = json.loads(clean_text)
            except Exception:
                start = clean_text.find("{")
                end = clean_text.rfind("}")
                if start != -1 and end != -1 and end > start:
                    sub = clean_text[start : end + 1]
                    sub = re.sub(r",\s*([}\]])", r"\1", sub)
                    parsed = json.loads(sub)
                else:
                    raise

            if isinstance(parsed, dict) and "name" in parsed and "steps" in parsed:
                parsed.setdefault("recipe_name", parsed.get("name"))
                parsed.setdefault("time", time_constraint)
                parsed.setdefault("meal_type", meal_type_clean)
                parsed.setdefault("ingredients_used", parsed.get("ingredients", ingredients))
                parsed.setdefault("pantry_staples", [])
                parsed.setdefault("nutrition_highlights", "Balanced Protein & Fiber")
                parsed.setdefault("chef_tip", "Taste and adjust seasoning before serving.")
                parsed.setdefault("category", f"Quick {meal_type_clean.capitalize()}")
                parsed.setdefault("area", "Chef Selection")
                parsed.setdefault("thumbnail", "")
                return parsed
        except Exception as exc:
            logger.warning("LLM recipe generation failed (%s), using dynamic chef engine.", exc)

    return _generate_heuristic_recipe(ingredients, time_constraint, meal_type_clean)


# Backward-compatible tool alias
@mcp.tool(name="get_recipe", description="Suggest a quick recipe based on available ingredients, time, and meal type")
def get_recipe(ingredients: list, time_constraint: str = "15 min", meal_type: str = "meal") -> dict:
    return get_meal_recipe(ingredients=ingredients, time_constraint=time_constraint, meal_type=meal_type)


class RecipeTool:
    """Tool class exposing recipe and meal generation methods."""

    def get_recipe(self, ingredients: list, time_constraint: str = "15 min", meal_type: str = "meal") -> dict:
        return get_meal_recipe(ingredients=ingredients, time_constraint=time_constraint, meal_type=meal_type)

    def get_meal_recipe(self, ingredients: list, time_constraint: str = "15 min", meal_type: str = "meal", cuisine_pref: str = None) -> dict:
        return get_meal_recipe(ingredients=ingredients, time_constraint=time_constraint, meal_type=meal_type, cuisine_pref=cuisine_pref)


if __name__ == "__main__":
    mcp.run()
