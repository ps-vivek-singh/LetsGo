"""Meal & Recipe Agent — specialist agent for breakfast, lunch, dinner, and snack meal planning."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from mcp_tools.recipe_tools import RecipeTool


def _parse_minutes(time_val: Any) -> int:
    """Extract an integer minute count from various formats ('10', '10 min', '15 minutes')."""
    if isinstance(time_val, int):
        return time_val
    m = re.search(r"(\d+)", str(time_val))
    return int(m.group(1)) if m else 15


def _make_steps(recipe_name: str, ingredients: list) -> list[str]:
    """Generate plausible steps when not provided."""
    ing_list = ", ".join(str(i) for i in ingredients) if ingredients else "your ingredients"
    return [
        f"Gather and prep your ingredients: {ing_list}.",
        "Season with a pinch of sea salt, black pepper, and olive oil.",
        f"Cook the {recipe_name} over medium heat, adjusting temperature as needed.",
        "Plate and garnish with fresh herbs. Serve immediately.",
    ]


class MealAgent:
    """Specialist agent for generating tailored recipes across breakfast, lunch, and dinner."""

    def __init__(self) -> None:
        self.tool = RecipeTool()

    def run(
        self,
        ingredients: Optional[List[str]] = None,
        time_constraint: str = "15 min",
        meal_type: str = "meal",
    ) -> str:
        """Return plain-text formatted meal idea for CLI output."""
        recipe = self.tool.get_meal_recipe(ingredients, time_constraint, meal_type=meal_type)
        m_title = (recipe.get("meal_type") or meal_type or "Meal").capitalize()
        lines = [
            f"## {m_title} Idea: {recipe.get('name')}",
            f"- Time: {recipe.get('time', time_constraint)} ({recipe.get('prep_time_minutes', 10)} min prep)",
            f"- Primary Ingredients: {', '.join(recipe.get('ingredients_used', ingredients or []))}",
        ]
        if recipe.get("pantry_staples"):
            lines.append(f"- Pantry Staples: {', '.join(recipe.get('pantry_staples', []))}")
        if recipe.get("nutrition_highlights"):
            lines.append(f"- Nutrition: {recipe.get('nutrition_highlights')}")
        if recipe.get("chef_tip"):
            lines.append(f"- Chef's Tip: {recipe.get('chef_tip')}")
        if recipe.get("steps"):
            lines.append("\n### Steps:")
            for i, step in enumerate(recipe["steps"], 1):
                lines.append(f"{i}. {step}")
        return "\n".join(lines)

    def run_structured(
        self,
        ingredients: Optional[List[str]] = None,
        time_constraint: str = "15 min",
        meal_type: str = "meal",
        cuisine_pref: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return typed dict matching structured API contract shape."""
        recipe: dict = self.tool.get_meal_recipe(
            ingredients, time_constraint, meal_type=meal_type, cuisine_pref=cuisine_pref
        )
        name: str = recipe.get("name") or recipe.get("recipe_name") or f"Quick {meal_type.capitalize()}"
        used: list = recipe.get("ingredients_used") or recipe.get("ingredients") or (ingredients or ["eggs"])
        prep: int = _parse_minutes(recipe.get("prep_time_minutes", recipe.get("time", time_constraint)))
        cook: int = _parse_minutes(recipe.get("cook_time_minutes", prep))
        total: int = recipe.get("total_time_minutes") or (prep + cook)

        steps: list = recipe.get("steps") or _make_steps(name, used)
        pantry: list = recipe.get("pantry_staples", ["olive oil", "salt", "pepper"])
        nutrition: str = recipe.get("nutrition_highlights", "Balanced Protein & Fiber")
        chef_tip: str = recipe.get("chef_tip", "Season to taste and serve fresh.")

        category: str = recipe.get("category", f"Quick {meal_type.capitalize()}")
        area: str = recipe.get("area", "Chef's Selection")
        thumbnail: str = recipe.get("thumbnail", "")

        # Alternate quick suggestion
        alt_name = f"Crispy {used[0] if used else 'Herb'} Bowl" if used else "Quick Protein Bowl"
        alternates = [
            {
                "recipe_name": alt_name,
                "prep_time_minutes": max(5, prep - 5),
            }
        ]

        return {
            "section": "breakfast",  # preserve canonical key for backward compatibility
            "status": "success",
            "data": {
                "name": name,
                "recipe_name": name,
                "meal_type": recipe.get("meal_type", meal_type),
                "prep_time_minutes": prep,
                "cook_time_minutes": cook,
                "total_time_minutes": total,
                "ingredients_used": used,
                "pantry_staples": pantry,
                "steps": steps,
                "nutrition_highlights": nutrition,
                "chef_tip": chef_tip,
                "alternates": alternates,
                "category": category,
                "area": area,
                "thumbnail": thumbnail,
            },
        }


# Alias for backward compatibility
BreakfastAgent = MealAgent
