from mcp_tools.recipe_tools import RecipeTool


class MealDBService:
    def __init__(self) -> None:
        self.tool = RecipeTool()

    def get_recipe(self, ingredients: list, time_constraint: str) -> dict:
        return self.tool.get_recipe(ingredients, time_constraint)
