import unittest

from agents.breakfast_agent import BreakfastAgent, MealAgent
from mcp_tools.recipe_tools import RecipeTool, get_meal_recipe
from agents.response_synthesizer import synthesize_response
from agents.reflection import ReflectionEngine


class MealAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = MealAgent()
        self.tool = RecipeTool()

    def test_meal_agent_alias(self):
        self.assertEqual(BreakfastAgent, MealAgent)

    def test_generate_breakfast_recipe(self):
        res = self.agent.run_structured(["eggs", "spinach"], "10 min", meal_type="breakfast")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["section"], "breakfast")
        data = res["data"]
        self.assertEqual(data["meal_type"], "breakfast")
        self.assertTrue(len(data["steps"]) >= 3)
        self.assertIn("eggs", " ".join(str(i) for i in data["ingredients_used"]).lower())

    def test_generate_lunch_recipe(self):
        res = self.agent.run_structured(["chicken", "rice"], "15 min", meal_type="lunch")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["meal_type"], "lunch")
        self.assertTrue(len(data["steps"]) >= 3)
        self.assertIn("chicken", " ".join(str(i) for i in data["ingredients_used"]).lower())

    def test_generate_dinner_recipe(self):
        res = self.agent.run_structured(["salmon", "garlic"], "20 min", meal_type="dinner")
        self.assertEqual(res["status"], "success")
        data = res["data"]
        self.assertEqual(data["meal_type"], "dinner")
        self.assertTrue(len(data["steps"]) >= 3)
        self.assertIn("salmon", " ".join(str(i) for i in data["ingredients_used"]).lower())

    def test_run_cli_output(self):
        text = self.agent.run(["paneer", "tomatoes"], "15 min", meal_type="dinner")
        self.assertIn("## Dinner Idea", text)
        self.assertIn("Primary Ingredients:", text)
        self.assertIn("Steps:", text)

    def test_minimal_pantry_staples(self):
        res = get_meal_recipe(["eggs"], "10 min", meal_type="breakfast")
        self.assertIn("pantry_staples", res)
        self.assertTrue(isinstance(res["pantry_staples"], list))

    def test_synthesizer_formats_meal_type(self):
        sections = {
            "breakfast": {
                "status": "success",
                "data": {
                    "name": "Pan-Seared Herb Salmon",
                    "meal_type": "dinner",
                    "prep_time_minutes": 15,
                    "ingredients_used": ["salmon", "spinach"],
                    "chef_tip": "Sear skin down first.",
                }
            }
        }
        intent = {"location": "London"}
        engine = ReflectionEngine()
        reflection = engine.reflect(sections, intent)
        summary = synthesize_response(sections, intent, reflection)
        self.assertIn("For dinner, try Pan-Seared Herb Salmon", summary)
        self.assertIn("featuring salmon, spinach", summary)


if __name__ == "__main__":
    unittest.main()
