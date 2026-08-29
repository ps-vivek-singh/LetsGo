import unittest

from nlp.query_parser import QueryParser


class QueryParserTests(unittest.TestCase):
    def test_extracts_sections_and_entities(self):
        parser = QueryParser()
        query = "I'm leaving from Chicago. Give me today's weather and UV, quick news, commute advice, and a 10-minute breakfast idea with eggs."

        result = parser.parse(query)

        self.assertEqual(result["location"], "Chicago")
        self.assertIn("weather", result["sections"])  # UV maps to weather section
        self.assertIn("news", result["sections"])
        self.assertIn("commute", result["sections"])
        self.assertIn("breakfast", result["sections"])
        self.assertIn("eggs", result["ingredients"])
        self.assertEqual(result["meal_type"], "breakfast")
        self.assertEqual(result["time_constraint"], "10 minutes")
        self.assertIn("leaving", result["travel_intent"])

    def test_extracts_meals_breakfast_lunch_dinner(self):
        parser = QueryParser()
        
        lunch_q = "Quick lunch with chicken and spinach under 15 minutes"
        res_lunch = parser.parse(lunch_q)
        self.assertEqual(res_lunch["meal_type"], "lunch")
        self.assertIn("chicken", res_lunch["ingredients"])
        self.assertIn("spinach", res_lunch["ingredients"])
        self.assertIn("breakfast", res_lunch["sections"])

        dinner_q = "Healthy dinner idea with salmon and asparagus"
        res_dinner = parser.parse(dinner_q)
        self.assertEqual(res_dinner["meal_type"], "dinner")
        self.assertIn("salmon", res_dinner["ingredients"])
        self.assertIn("asparagus", res_dinner["ingredients"])

        snack_q = "Quick snack using banana and peanut butter"
        res_snack = parser.parse(snack_q)
        self.assertEqual(res_snack["meal_type"], "snack")
        self.assertIn("banana", res_snack["ingredients"])

    def test_extracts_itinerary_queries(self):
        parser = QueryParser()
        q = "Give me a 3-day itinerary for London"
        res = parser.parse(q)
        self.assertEqual(res["location"], "London")
        self.assertEqual(res["days"], 3)
        self.assertIn("itinerary", res["sections"])


if __name__ == "__main__":
    unittest.main()
