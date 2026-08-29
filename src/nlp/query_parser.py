import re
from typing import Dict, List


class QueryParser:
    """Keyword-based NLP parser for intent, location, destination, ingredients, and time.

    Extracts structured intent from free-text user queries including:
      - sections (weather, news, commute, breakfast)
      - origin location (city the user is in / starting from)
      - destination (place the user is going to — used for commute routing)
      - ingredients (for breakfast recipes)
      - time constraint (e.g. "10 minutes")
      - travel intent words
    """

    def __init__(self) -> None:
        # Use whole-word patterns to avoid substring false-positives (e.g. "eat" inside "weather")
        self.section_keywords = {
            "weather":   [r"\bweather\b", r"\bforecast\b", r"\btemperature\b", r"\btemp\b",
                          r"\brain\b", r"\bsunny\b", r"\bcloudy\b", r"\buv\b", r"\bsun\b",
                          r"\bumbrella\b", r"\braincoat\b", r"\bchilly\b", r"\bfreezing\b",
                          r"\bheatwave\b", r"\bblizzard\b", r"\bsnow\b"],
            "news":      [r"\bnews\b", r"\bheadlines\b", r"\bheadline\b", r"\blatest\b",
                          r"(?<!traffic\s)(?<!transit\s)\bupdates?\b"],
            "commute":   [r"\bcommute\b", r"\bcommuting\b", r"\btraffic\b", r"\btransit\b",
                          r"\broute\b", r"\bdrive\b", r"\bdriving\b",
                          r"\bbus\b", r"\btrain\b", r"\btube\b", r"\bsubway\b", r"\bmetro\b",
                          r"\bbike\b", r"\bcycling\b", r"\bwalk\b", r"\bwalking\b", r"\beta\b",
                          r"\bgoing to\s+(?!rain|snow|be|hail|freeze)\b",
                          r"\bheading to\b", r"\bheading out to\b", r"\bheading out\b", r"\bdrop me\b"],
            "breakfast": [
                r"\bbreakfast\b", r"\blunch\b", r"\bdinner\b", r"\bsupper\b",
                r"\bbrunch\b", r"\bsnack\b", r"\bmeal\b", r"\bmeals\b", r"\brecipe\b",
                r"\beat\b", r"\bfood\b", r"\bcook\b", r"\bcooking\b",
                r"\bquick bite\b", r"\bdish\b", r"\beggs?\b", r"\btoast\b",
                r"\boats\b", r"\bporridge\b",
            ],
            "itinerary": [
                r"\bitinerary\b", r"\bitineraries\b", r"\btrip\b", r"\btravel plan\b",
                r"\bsightseeing\b", r"\bvacation\b", r"\btourist\b", r"\bplaces to visit\b",
                r"\bday plan\b", r"\bholiday\b", r"\btour\b", r"\bvisit\b",
                r"\bexplore\b", r"\bthings to do\b", r"\bplaces to see\b",
                r"\bgetaway\b", r"\btravel guide\b", r"\bjourney\b",
            ],
        }
        self.ingredient_keywords = [
            "eggs", "egg", "toast", "banana", "oat", "oats", "milk",
            "cheese", "bread", "avocado", "spinach", "tomato", "tomatoes",
            "chicken", "salmon", "paneer", "tofu", "rice", "pasta", "beef",
            "pork", "fish", "potato", "potatoes", "onion", "onions", "garlic",
            "mushroom", "mushrooms", "bell pepper", "peppers", "carrot", "carrots",
            "broccoli", "beans", "lentils", "yogurt", "butter", "lemon", "oil",
            "shrimp", "turkey", "bacon", "sausage", "tuna",
        ]
        self.travel_words = [
            "leaving", "heading out", "going to work", "going", "leave", "out",
        ]

    def parse(self, query: str) -> Dict[str, object]:
        normalized = query.lower().strip()
        sections        = self._extract_sections(normalized)
        location        = self._extract_location(query)
        destination     = self._extract_destination(query)
        ingredients     = self._extract_ingredients(normalized)
        meal_type       = self._extract_meal_type(normalized)
        time_constraint = self._extract_time_constraint(normalized)
        travel_intent   = self._extract_travel_intent(normalized)
        days            = self._extract_days(normalized)
        budget          = self._extract_budget(normalized)

        # If no explicit origin location was found but destination was extracted,
        # treat destination as the location
        if destination and (not location or location == "current location"):
            location = destination
            destination = ""

        if destination and location and destination.lower() == location.lower():
            destination = ""

        return {
            "location":        location,
            "destination":     destination,
            "sections":        sections,
            "ingredients":     ingredients,
            "meal_type":       meal_type,
            "time_constraint": time_constraint,
            "travel_intent":   travel_intent,
            "days":            days,
            "budget":          budget,
            "raw_query":       query,
        }

    def _extract_excluded_sections(self, normalized: str) -> List[str]:
        excluded = []
        neg_patterns = [
            r"\b(?:don't|do not|no|skip|without|exclude|omit|leave out|except|never mind)\s+(?:need\s+|want\s+|give\s+me\s+|include\s+)?(?:any\s+|the\s+)?([a-z\s]+?)(?=\s+(?:and|but|just|only|give|show|for|with|,)|$)",
            r"\b(?:no|without)\s+([a-z]+)\b",
            r"\b(?:already\s+ate|already\s+had)\b",
        ]
        if re.search(r"\b(?:already\s+ate|already\s+had)\b", normalized):
            excluded.append("breakfast")

        for pat in neg_patterns[:2]:
            for m in re.finditer(pat, normalized):
                chunk = m.group(1).strip()
                for sec_name, patterns in self.section_keywords.items():
                    if any(re.search(p, chunk) for p in patterns):
                        excluded.append(sec_name)
        return list(dict.fromkeys(excluded))

    def _extract_sections(self, normalized: str) -> List[str]:
        found = []
        is_travel_query = bool(re.search(r"\b(?:vacation|itinerary|trip|getaway|holiday|tourist)\b", normalized))
        excluded = self._extract_excluded_sections(normalized)

        for name, patterns in self.section_keywords.items():
            if name in excluded:
                continue

            # If it's a vacation/itinerary query and "food" is matched without cooking verbs, skip breakfast
            if name == "breakfast" and is_travel_query:
                if not re.search(r"\b(?:cook|cooking|recipe|breakfast|dinner|lunch|snack|dish|ingredients)\b", normalized):
                    continue

            # Match keywords only if not directly negated
            matched = False
            for pat in patterns:
                for m in re.finditer(pat, normalized):
                    start = m.start()
                    preceding = normalized[max(0, start - 30):start]
                    if re.search(r"\b(?:no|not|don't|do not|skip|without|exclude|omit|leave out)\s+(?:any\s+|the\s+)?$", preceding):
                        continue
                    matched = True
                    break
                if matched:
                    break

            if matched:
                found.append(name)

        found = [s for s in found if s not in excluded]

        # Out-of-scope intent guard
        out_of_scope_prefixes = ("translate", "calculate", "convert", "solve", "write python", "write code", "who is", "who was", "stock price", "stock of", "market cap")
        if any(normalized.startswith(p) for p in out_of_scope_prefixes):
            return []

        # Only trigger full default briefing if explicitly requested or when no sections found with morning/briefing greeting
        if any(w in normalized for w in ("full briefing", "full report", "everything", "all sections", "start my day", "daily routine")):
            fallback = ["weather", "news", "commute", "breakfast"]
            for s in fallback:
                if s not in excluded and s not in found:
                    found.append(s)
        elif not found and any(w in normalized for w in ("briefing", "morning", "good morning", "daily report")):
            fallback = ["weather", "news", "commute", "breakfast"]
            for s in fallback:
                if s not in excluded and s not in found:
                    found.append(s)

        return list(dict.fromkeys(found))

    def _extract_days(self, normalized: str) -> int:
        match = re.search(r"(\d+)\s*-?\s*days?", normalized)
        if match:
            return max(1, min(int(match.group(1)), 7))
        match = re.search(r"(\d+)\s*-?\s*weeks?", normalized)
        if match:
            return max(1, min(int(match.group(1)) * 7, 7))
        return 2

    def _extract_budget(self, normalized: str) -> str:
        if any(w in normalized for w in ("luxury", "premium", "high end", "expensive")):
            return "luxury"
        if any(w in normalized for w in ("moderate", "mid range", "mid-range", "average")):
            return "moderate"
        if any(w in normalized for w in ("budget", "cheap", "low cost", "affordable", "backpack")):
            return "budget"
        return "moderate"

    def _extract_destination(self, query: str) -> str:
        _dest_noise = {"work", "office", "school", "college", "home", "my", "the", "a", "an", "budget", "moderate", "luxury", "cheap"}

        match = re.search(
            r"\bfrom\s+(?:the\s+)?([a-zA-Z\s,]+?)\s+to\s+([a-zA-Z\s,]+?)(?:\s+(?:today|tomorrow|this|please|and|how|for|in\s+a|with|,|$)|\s*$)",
            query, re.IGNORECASE,
        )
        if match:
            dest = match.group(2).strip().rstrip(",")
            words = [w for w in dest.split() if w.lower() not in _dest_noise]
            if words:
                return " ".join(words).title()

        match = re.search(
            r"\b(?:heading(?:\s+out)?|going)\s+to\s+([a-zA-Z\s,]+?)(?:\s+(?:today|tomorrow|this|please|and|how|for|in\s+a|with|,|$)|\s*$)",
            query, re.IGNORECASE,
        )
        if match:
            dest = match.group(1).strip().rstrip(",")
            words = [w for w in dest.split() if w.lower() not in _dest_noise]
            if words:
                return " ".join(words).title()

        # If this is an itinerary query (e.g. "plan a trip to Bali"), don't treat it as a commute destination
        if not re.search(r"\b(?:trip|vacation|itinerary|sightseeing|travel plan)\b", query, re.IGNORECASE):
            match = re.search(
                r"\bto\s+([a-zA-Z\s,]+?)(?:\s+(?:today|tomorrow|this|please|and|how|for|in\s+a|with|,|$)|\s*$)",
                query, re.IGNORECASE,
            )
            if match:
                dest = match.group(1).strip().rstrip(",")
                words = [w for w in dest.split() if w.lower() not in _dest_noise]
                if words:
                    return " ".join(words).title()

        return ""

    def _extract_location(self, query: str) -> str:
        _noise = {
            "give", "get", "show", "tell", "please", "today", "tomorrow", "this",
            "weather", "news", "commute", "breakfast", "full", "quick", "briefing",
            "everything", "all", "plan", "headline", "headlines", "latest", "update",
            "updates", "traffic", "transit", "travel", "route", "drive", "driving",
            "food", "recipe", "eat", "cook", "ingredients", "time", "day", "days", "the", "a", "an",
            "i", "me", "my", "our", "you", "your", "what", "is", "of", "in", "from", "at", "for", "s",
            "trip", "vacation", "itinerary", "budget", "moderate", "luxury", "cheap",
            "morning", "evening", "afternoon", "night", "forecast", "report"
        }

        # Pattern 0: "trip to <Location>" / "itinerary for <Location>" / "vacation in/to <Location>"
        match = re.search(
            r"\b(?:trip\s+to|itinerary\s+for|vacation\s+(?:in|to)|getaway\s+(?:vacation\s+)?to|travel\s+to|visit)\s+([a-zA-Z\s,]+?)(?=\s+(?:for\s+\d+|in\s+a|with|on|at|today|tomorrow|this|please|and|,)|[\s.,!?:;]*$)",
            query, re.IGNORECASE,
        )
        if match:
            loc = match.group(1).strip(" .,!?:;")
            words = [w for w in loc.split() if w.lower() not in _noise and not re.match(r"^\d+-days?$", w.lower())]
            if words:
                return " ".join(words).title()

        # Pattern 1: "from <origin> to <destination>"
        match = re.search(
            r"\bfrom\s+(?:the\s+)?([a-zA-Z\s,]+?)\s+to\b",
            query, re.IGNORECASE,
        )
        if match:
            loc = match.group(1).strip(" .,!?:;")
            words = [w for w in loc.split() if w.lower() not in _noise and not re.match(r"^\d+-days?$", w.lower())]
            if words:
                return " ".join(words).title()

        # Pattern 2: "from/in/for/at/of <Location>"
        match = re.search(
            r"\b(?:forecast\s+in|weather\s+in|from|in|for|at|of)\s+([a-zA-Z\s]+?)(?=\s+(?:to|today|tomorrow|this|give|get|show|tell|please|and|with|how|,)|[\s.,!?:;]*$)",
            query, re.IGNORECASE,
        )
        if match:
            loc = match.group(1).strip(" .,!?:;")
            words = [w for w in loc.split() if w.lower() not in _noise and not re.match(r"^\d+-days?$", w.lower())]
            if words:
                return " ".join(words).title()

        # Fallback word scanner
        words = query.split()
        for i, w in enumerate(words):
            clean = w.strip('.,!?:;"\'-').lower()
            if (clean not in _noise and len(clean) > 2 and "'" not in clean
                    and not re.match(r"^\d+-days?$", clean)
                    and clean not in self.ingredient_keywords
                    and clean not in self.travel_words):
                loc = w.strip('.,!?:;"\'-').title()
                if i + 1 < len(words):
                    next_w = words[i+1].strip('.,!?:;"\'-')
                    if (next_w.lower() not in _noise and len(next_w) > 2
                            and not re.match(r"^\d+-days?$", next_w.lower())
                            and "'" not in next_w and next_w.lower() not in self.ingredient_keywords):
                        loc = f"{loc} {next_w.title()}"
                return loc

        return "current location"

    def _extract_meal_type(self, normalized: str) -> str:
        if re.search(r"\b(?:dinner|supper|evening meal)\b", normalized):
            return "dinner"
        if re.search(r"\b(?:lunch|brunch|midday meal)\b", normalized):
            return "lunch"
        if re.search(r"\b(?:breakfast|morning meal)\b", normalized):
            return "breakfast"
        if re.search(r"\b(?:snack|quick bite|appetizer)\b", normalized):
            return "snack"
        return "meal"

    def _extract_ingredients(self, normalized: str) -> List[str]:
        found = []
        non_food = {
            "weather", "commute", "news", "briefing", "traffic", "itinerary",
            "forecast", "headlines", "update", "temperature", "transit", "route",
            "destination", "today", "tomorrow", "tonight", "morning", "evening",
        }

        patterns = [
            r"(?:breakfast|lunch|dinner|supper|snack|meal|recipe|cook|cooking|dish|make|food)\s+(?:with|using|of|having)\s+([a-zA-Z\s,&\+]+?)(?:\s+(?:under|in\s+\d+|for|today|tomorrow|please|and\s+commute|and\s+weather|and\s+news)|$|\.)",
            r"(?:cook\s+with|using|have|with)\s+([a-zA-Z\s,&\+]+?)(?:\s+(?:under|in\s+\d+|for\s+(?:breakfast|lunch|dinner|snack|meal)|today|tomorrow|please)|$|\.)",
        ]
        for p in patterns:
            m = re.search(p, normalized)
            if m:
                raw_chunk = m.group(1)
                parts = re.split(r",|\band\b|&|\+", raw_chunk)
                for part in parts:
                    cleaned = part.strip(" .,!?")
                    cleaned = re.sub(r"^(?:some|a|an|few|my|the|fresh|leftover|quick|healthy|tasty)\s+", "", cleaned)
                    cleaned = re.sub(r"^(?:breakfast|lunch|dinner|snack|meal|dish)\s+(?:with|using)?\s*", "", cleaned)
                    if any(n in cleaned for n in non_food):
                        continue
                    if cleaned and len(cleaned) > 2 and cleaned not in ("minutes", "minute", "hours", "hour", "today", "quick", "breakfast", "lunch", "dinner", "snack", "meal", "food"):
                        if cleaned not in found and not any(cleaned == f for f in found):
                            found.append(cleaned)

        for ingredient in self.ingredient_keywords:
            if re.search(rf"\b{re.escape(ingredient)}\b", normalized):
                if ingredient not in found and not any(ingredient in f for f in found):
                    found.append(ingredient)
        return found

    def _extract_time_constraint(self, normalized: str) -> str:
        match = re.search(r"(\d+)\s*-?\s*min(?:ute)?s?\b", normalized)
        if match:
            return f"{match.group(1)} minutes"
        return "no specific time"

    def _extract_travel_intent(self, normalized: str) -> List[str]:
        found = []
        for word in self.travel_words:
            if word in normalized:
                found.append(word)
        return found or ["daily routine"]
