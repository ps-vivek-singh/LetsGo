"""Travel Itinerary FastMCP Tool Server — generates itemized travel plans using LLM or destination engine."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from services.config import Config
from services.llm_client import LLMClient

logger = logging.getLogger("commute_commander.itinerary_tools")

mcp = FastMCP("itinerary-server")

# ── Authentic Destination Knowledge Base (Rich Fallback Engine) ───────────────
_CURATED_DESTINATIONS: Dict[str, Dict[str, Any]] = {
    "bali": {
        "location": "Bali, Indonesia",
        "budget_estimates": {"budget": "$35 - $60 / day", "moderate": "$90 - $160 / day", "luxury": "$280+ / day"},
        "days": [
            {
                "day_number": 1,
                "theme": "Sacred Temples & Cultural Ubud",
                "morning": {"activity": "Explore Ubud Sacred Monkey Forest & Puri Saren Royal Palace", "location": "Central Ubud", "time": "08:30 - 11:30 AM"},
                "afternoon": {"activity": "Stroll the Tegalalang Rice Terraces and coffee plantation tasting", "location": "Tegalalang Valley", "time": "12:30 - 04:00 PM"},
                "evening": {"activity": "Watch sunset Kecak Dance & wander Ubud Art Market", "location": "Taman Saraswati Temple", "time": "05:30 - 08:30 PM"},
                "dining": {"lunch": "Bebek Bengil (Famous Balinese Crispy Duck)", "dinner": "Warung Babi Guling Ibu Oka (Roasted Suckling Pig)"},
            },
            {
                "day_number": 2,
                "theme": "Southern Cliffs & Sunset Beaches",
                "morning": {"activity": "Relax and surf at Padang Padang & Bingin Beach", "location": "Uluwatu Peninsula", "time": "09:00 - 12:00 PM"},
                "afternoon": {"activity": "Visit cliffside Pura Luhur Uluwatu Temple overlooking the Indian Ocean", "location": "Uluwatu Cliffs", "time": "01:30 - 05:00 PM"},
                "evening": {"activity": "Candlelight beachfront sunset dinner on the sand", "location": "Jimbaran Bay", "time": "05:30 - 08:30 PM"},
                "dining": {"lunch": "Single Fin Clifftop Café", "dinner": "Fresh Grilled Seafood on Jimbaran Beach"},
            },
            {
                "day_number": 3,
                "theme": "Iconic Sea Temples & Seminyak Vibe",
                "morning": {"activity": "Visit the floating ocean temple of Pura Tanah Lot", "location": "Tabanan Coast", "time": "08:30 - 11:30 AM"},
                "afternoon": {"activity": "Boutique shopping, spa treatment & café hopping in Seminyak", "location": "Kayu Aya / Oberoi", "time": "01:00 - 04:30 PM"},
                "evening": {"activity": "Sunset cocktails at Potato Head Beach Club & oceanfront lounge", "location": "Petitenget Beach, Seminyak", "time": "05:30 - 09:00 PM"},
                "dining": {"lunch": "Sisterfields All-Day Brunch", "dinner": "Merah Putih (Modern Indonesian fine dining)"},
            },
            {
                "day_number": 4,
                "theme": "Volcano Sunrise & Water Palaces",
                "morning": {"activity": "Sunrise trek at Mount Batur and volcanic hot springs soak", "location": "Kintamani", "time": "05:00 - 10:30 AM"},
                "afternoon": {"activity": "Explore Tirta Gangga Royal Water Garden and stepping stones", "location": "East Bali (Karangasem)", "time": "12:30 - 04:00 PM"},
                "evening": {"activity": "Quiet seaside walk along black sand volcanic coast", "location": "Amed Coastline", "time": "05:30 - 08:00 PM"},
                "dining": {"lunch": "Grand Puncak Sari with panoramic volcano view", "dinner": "Warung Enak East Bali Specialties"},
            },
        ],
        "travel_tips": [
            "Hire a private driver (approx. $40/day) or use Grab/Gojek for seamless island travel.",
            "Wear a sarong and sash when visiting sacred Balinese Hindu temples (usually rentable on-site).",
            "Exchange currency only at authorized money changers (BMC or Central Kuta) with clear receipts.",
        ],
    },
    "paris": {
        "location": "Paris, France",
        "budget_estimates": {"budget": "€60 - €95 / day", "moderate": "€140 - €240 / day", "luxury": "€450+ / day"},
        "days": [
            {
                "day_number": 1,
                "theme": "Classic Icons & Historic Seine",
                "morning": {"activity": "Climb the Eiffel Tower and stroll Champ de Mars", "location": "7th Arrondissement", "time": "09:00 - 11:30 AM"},
                "afternoon": {"activity": "Explore masterworks at the Louvre Museum & Tuileries Garden", "location": "1st Arrondissement", "time": "12:30 - 04:30 PM"},
                "evening": {"activity": "Seine River twilight boat cruise and Île de la Cité walk", "location": "Pont Neuf / Notre-Dame", "time": "06:00 - 09:00 PM"},
                "dining": {"lunch": "Le Comptoir de la Gastronomie (Classic French bistro)", "dinner": "Bistrot Paul Bert (Steak frites & soufflé)"},
            },
            {
                "day_number": 2,
                "theme": "Bohemian Montmartre & Latin Quarter",
                "morning": {"activity": "Wander Montmartre alleys and visit Sacré-Cœur Basilica", "location": "18th Arrondissement", "time": "09:00 - 11:30 AM"},
                "afternoon": {"activity": "Browse Shakespeare and Company and Pantheon in the Latin Quarter", "location": "5th Arrondissement", "time": "01:00 - 04:30 PM"},
                "evening": {"activity": "Sunset view from Arc de Triomphe and stroll Champs-Élysées", "location": "8th Arrondissement", "time": "06:00 - 08:30 PM"},
                "dining": {"lunch": "La Maison Rose (Montmartre café)", "dinner": "Bouillon Chartier (Historic Belle Époque brasserie)"},
            },
        ],
        "travel_tips": [
            "Book Louvre and Eiffel Tower time slots at least 2 weeks in advance.",
            "Use the Navigo Easy card or metro ticket packs for efficient city transit.",
            "Always greet shopkeepers with 'Bonjour Madame/Monsieur' for courteous service.",
        ],
    },
    "tokyo": {
        "location": "Tokyo, Japan",
        "budget_estimates": {"budget": "¥7,000 - ¥12,000 / day", "moderate": "¥18,000 - ¥30,000 / day", "luxury": "¥60,000+ / day"},
        "days": [
            {
                "day_number": 1,
                "theme": "Tradition & Neon Metropolises",
                "morning": {"activity": "Visit historic Sensō-ji Temple and Nakamise shopping street", "location": "Asakusa", "time": "08:30 - 11:30 AM"},
                "afternoon": {"activity": "Cross world-famous Shibuya Scramble & visit Meiji Jingu Shrine", "location": "Shibuya & Harajuku", "time": "12:30 - 04:30 PM"},
                "evening": {"activity": "Take in skyline views from Tokyo Metropolitan Gov building & Omoide Yokocho", "location": "Shinjuku", "time": "05:30 - 09:00 PM"},
                "dining": {"lunch": "Ichiran Ramen or Asakusa Imahan (Sukiyaki)", "dinner": "Yakitori Alley skewers in Omoide Yokocho"},
            },
            {
                "day_number": 2,
                "theme": "Modern Tech, Anime & Waterfront",
                "morning": {"activity": "Experience interactive digital art at teamLab Planets", "location": "Toyosu", "time": "09:00 - 12:00 PM"},
                "afternoon": {"activity": "Explore electronic stores, manga centers & themed cafés", "location": "Akihabara", "time": "01:30 - 05:00 PM"},
                "evening": {"activity": "Stroll Rainbow Bridge waterfront and Odaiba Seaside Park", "location": "Odaiba", "time": "06:00 - 08:30 PM"},
                "dining": {"lunch": "Fresh Tuna Donburi at Toyosu Outer Market", "dinner": "Ginza Kagari (Rich Chicken Paitan Ramen)"},
            },
        ],
        "travel_tips": [
            "Load an IC card (Suica / Pasmo) onto Apple Wallet or Google Wallet for easy train tap-and-go.",
            "Carry a small amount of cash; smaller ramen shops and coin lockers still prefer Yen coins/bills.",
            "Remember that tipping is not customary in Japan.",
        ],
    },
}


def _match_curated_destination(location: str) -> Optional[Dict[str, Any]]:
    """Match query against known rich destinations."""
    loc_lower = location.lower()
    for key, data in _CURATED_DESTINATIONS.items():
        if key in loc_lower or loc_lower in key:
            return data
    return None


def _generate_heuristic_itinerary(
    location: str, days: int, budget: str, interests: List[str]
) -> Dict[str, Any]:
    """Generate structured fallback itinerary using rich curated knowledge base or dynamic generator."""
    loc_clean = location.strip().title() if location and location.strip() else "Travel Destination"
    budget_clean = budget.lower().strip() if budget else "moderate"

    curated = _match_curated_destination(location)
    if curated:
        curated_days = curated["days"]
        selected_days = []
        for d in range(1, min(days + 1, 8)):
            template_day = curated_days[(d - 1) % len(curated_days)]
            new_day = dict(template_day)
            new_day["day_number"] = d
            selected_days.append(new_day)

        estimates = curated["budget_estimates"]
        cost_str = estimates.get(budget_clean, "$100 - $180 / day")
        return {
            "location": curated["location"],
            "days_count": len(selected_days),
            "budget": budget_clean,
            "interests": interests or ["Sightseeing", "Culture", "Food"],
            "estimated_cost": cost_str,
            "days": selected_days,
            "travel_tips": curated["travel_tips"],
        }

    # Dynamic contextual generation for any other city with unique day-by-day activities
    day_schedules = [
        {
            "theme": f"Historic Core & Signature Landmarks of {loc_clean}",
            "morning": {
                "activity": f"Guided morning walking tour through historical cobblestone streets & central heritage plaza in {loc_clean}",
                "location": f"Old Town Plaza & Main Square, {loc_clean}",
                "time": "08:30 - 11:30 AM",
            },
            "afternoon": {
                "activity": f"Explore iconic architectural monuments, grand cathedrals, and central museum exhibits",
                "location": f"Historic Heritage Quarter, {loc_clean}",
                "time": "12:30 - 04:00 PM",
            },
            "evening": {
                "activity": f"Golden hour sunset stroll along scenic waterfront promenade followed by ambient dinner",
                "location": f"Riverfront / Old Town Promenade, {loc_clean}",
                "time": "05:30 - 08:30 PM",
            },
            "dining": {
                "lunch": f"Charming heritage café with authentic regional lunch plates ({budget_clean} budget)",
                "dinner": f"Historic tavern serving signature traditional dishes of {loc_clean}",
            },
        },
        {
            "theme": f"Art, Architecture & Cultural Neighborhoods of {loc_clean}",
            "morning": {
                "activity": f"Visit renowned fine arts gallery and surrounding sculpture gardens in {loc_clean}",
                "location": f"Arts & Cultural District, {loc_clean}",
                "time": "09:00 - 11:30 AM",
            },
            "afternoon": {
                "activity": f"Discover bohemian artisan alleys, historic libraries, and boutique design studios",
                "location": f"Latin / Creative Quarter, {loc_clean}",
                "time": "12:30 - 04:30 PM",
            },
            "evening": {
                "activity": f"Attend an evening theater performance or live acoustic lounge session",
                "location": f"Performing Arts Center, {loc_clean}",
                "time": "06:00 - 09:00 PM",
            },
            "dining": {
                "lunch": f"Bustling museum terrace bistro with artisanal salads & espresso",
                "dinner": f"Modern culinary bistro featuring seasonal fusion fare in {loc_clean}",
            },
        },
        {
            "theme": f"Scenic Viewpoints, Parks & Hidden Courtyards",
            "morning": {
                "activity": f"Sunrise morning walk through botanical gardens and hilltop panoramic viewpoint",
                "location": f"City Hilltop Gardens, {loc_clean}",
                "time": "08:00 - 11:00 AM",
            },
            "afternoon": {
                "activity": f"Uncover secret courtyard gardens, historic passageways, and local craft workshops",
                "location": f"Garden District, {loc_clean}",
                "time": "12:00 - 03:30 PM",
            },
            "evening": {
                "activity": f"Panoramic cocktail experience on a high-altitude rooftop lounge overlooking {loc_clean}",
                "location": f"Skyline Observation Lounge, {loc_clean}",
                "time": "05:30 - 08:30 PM",
            },
            "dining": {
                "lunch": f"Garden pavilion eatery serving organic farm-fresh bowls",
                "dinner": f"High-floor restaurant offering panoramic city night views",
            },
        },
        {
            "theme": f"Local Gastronomy & Evening Entertainment",
            "morning": {
                "activity": f"Immersive culinary market walk & fresh ingredient tasting tour",
                "location": f"Central Food Market, {loc_clean}",
                "time": "09:00 - 11:30 AM",
            },
            "afternoon": {
                "activity": f"Specialty food hall exploration, artisan chocolate tasting & pastry workshop",
                "location": f"Gourmet Passage, {loc_clean}",
                "time": "01:00 - 04:30 PM",
            },
            "evening": {
                "activity": f"Vibrant night market discovery & speakeasy lounge pub crawl in {loc_clean}",
                "location": f"Night Market District, {loc_clean}",
                "time": "06:00 - 09:30 PM",
            },
            "dining": {
                "lunch": f"Market stall crawl trying regional street-food delicacies",
                "dinner": f"Chef's tasting menu at a top-rated local gastronomy restaurant",
            },
        },
        {
            "theme": f"Day Excursion & Natural Wonders near {loc_clean}",
            "morning": {
                "activity": f"Scenic day excursion to nearby mountain trails, coastal cliffs or lake shorelines near {loc_clean}",
                "location": f"Regional Nature Reserve, {loc_clean}",
                "time": "08:00 - 11:30 AM",
            },
            "afternoon": {
                "activity": f"Outdoor adventure: coastal kayak, scenic nature trek, or historic castle estate tour",
                "location": f"Outer Scenic Valley, {loc_clean}",
                "time": "12:30 - 04:30 PM",
            },
            "evening": {
                "activity": f"Relaxing fireside dinner or waterfront sunset viewing by the bay",
                "location": f"Lakeside / Coastal Pier, {loc_clean}",
                "time": "05:30 - 08:30 PM",
            },
            "dining": {
                "lunch": f"Rustic countryside inn serving hearty mountain/coastal lunches",
                "dinner": f"Seafood / farm-to-table grill with sunset water views",
            },
        },
        {
            "theme": f"Local Markets, Boutiques & Artisan Quarter",
            "morning": {
                "activity": f"Morning shopping spree through local artisan bazaars & flea markets",
                "location": f"Artisan Flea Market, {loc_clean}",
                "time": "09:00 - 11:30 AM",
            },
            "afternoon": {
                "activity": f"Browse vintage boutiques, antique galleries, and handcrafted leather/textile shops",
                "location": f"Fashion & Antique Boulevard, {loc_clean}",
                "time": "01:00 - 04:30 PM",
            },
            "evening": {
                "activity": f"Atmospheric evening stroll through candlelit historic alleys and live jazz venue",
                "location": f"Old Quarter Jazz Club, {loc_clean}",
                "time": "06:00 - 09:30 PM",
            },
            "dining": {
                "lunch": f"Trendy courtyard espresso bar with wood-fired sourdough pizzas",
                "dinner": f"Cellar bistro known for intimate ambiance and local wines",
            },
        },
        {
            "theme": f"Panoramic Farewell & Sunset Highlights",
            "morning": {
                "activity": f"Relaxing thermal spa morning session or peaceful park reflection in {loc_clean}",
                "location": f"Central City Baths & Park, {loc_clean}",
                "time": "09:00 - 11:30 AM",
            },
            "afternoon": {
                "activity": f"Final landmark souvenir shopping and top city observatory deck visit",
                "location": f"Panoramic City Tower, {loc_clean}",
                "time": "12:30 - 04:00 PM",
            },
            "evening": {
                "activity": f"Grand farewell twilight harbor cruise with illuminated city skyline views",
                "location": f"Main Harbor / Bridge, {loc_clean}",
                "time": "05:30 - 09:00 PM",
            },
            "dining": {
                "lunch": f"Waterfront harbor cafe with fresh pastries & coffee",
                "dinner": f"Award-winning farewell celebration dinner overlooking the city",
            },
        },
    ]

    days_list = []
    for d in range(1, min(days + 1, 8)):
        template = day_schedules[(d - 1) % len(day_schedules)]
        day_item = {
            "day_number": d,
            "theme": template["theme"],
            "morning": dict(template["morning"]),
            "afternoon": dict(template["afternoon"]),
            "evening": dict(template["evening"]),
            "dining": dict(template["dining"]),
        }
        days_list.append(day_item)

    budget_estimates = {
        "budget": "$40 - $70 / day",
        "moderate": "$100 - $180 / day",
        "luxury": "$300+ / day",
    }

    return {
        "location": loc_clean,
        "days_count": days,
        "budget": budget_clean,
        "interests": interests,
        "estimated_cost": budget_estimates.get(budget_clean, "$100 - $180 / day"),
        "days": days_list,
        "travel_tips": [
            f"Check operating hours and online advance ticketing for major {loc_clean} attractions.",
            "Use local metro or ride-sharing apps for economical transportation.",
            "Keep emergency contact numbers and digital copies of travel documents accessible.",
        ],
    }


@mcp.tool(
    name="get_itinerary",
    description="Generate a detailed day-by-day travel itinerary with morning/afternoon/evening schedules, dining spots, and travel tips.",
)
def get_itinerary(
    location: str,
    days: int = 2,
    budget: str = "moderate",
    interests: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """FastMCP tool to generate itemized travel itineraries via LLM or rich engine."""
    if not location or not location.strip():
        location = "Bali Indonesia"

    days = max(1, min(int(days), 7))
    if not interests:
        interests = ["Sightseeing", "Food", "Culture"]

    llm = LLMClient()
    if llm.is_available():
        try:
            prompt = (
                f"You are a premier worldwide travel consultant. Generate a {days}-day travel itinerary for {location} with a {budget} budget.\n"
                f"Interests: {', '.join(interests)}.\n\n"
                f"Requirements:\n"
                f"- Include real, specific landmark names, neighborhoods, authentic local dishes, and famous restaurants in {location}.\n"
                f"- Provide vivid, engaging activity descriptions.\n\n"
                f"Output MUST be pure valid JSON with this exact structure:\n"
                f"{{\n"
                f'  "location": "{location}",\n'
                f'  "days_count": {days},\n'
                f'  "budget": "{budget}",\n'
                f'  "interests": {json.dumps(interests)},\n'
                f'  "estimated_cost": "$... / day",\n'
                f'  "days": [\n'
                f"    {{\n"
                f'      "day_number": 1,\n'
                f'      "theme": "Descriptive Day Theme",\n'
                f'      "morning": {{"activity": "Specific activity description", "location": "Specific place name", "time": "09:00 - 11:30 AM"}},\n'
                f'      "afternoon": {{"activity": "Specific activity description", "location": "Specific place name", "time": "12:30 - 04:00 PM"}},\n'
                f'      "evening": {{"activity": "Specific activity description", "location": "Specific place name", "time": "05:30 - 08:30 PM"}},\n'
                f'      "dining": {{"lunch": "Real restaurant / dish recommendation", "dinner": "Real restaurant / dish recommendation"}}\n'
                f"    }}\n"
                f"  ],\n"
                f'  "travel_tips": ["Actionable local tip 1", "Actionable local tip 2", "Actionable local tip 3"]\n'
                f"}}"
            )
            response = llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional travel planner. You MUST reply with valid JSON only. Do not include markdown codeblocks or conversational text.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            content = response["choices"][0]["message"]["content"].strip()
            # Clean markdown code block fences if present
            clean_content = content
            if "```" in clean_content:
                match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean_content, re.IGNORECASE)
                if match:
                    clean_content = match.group(1).strip()
                else:
                    clean_content = re.sub(r"^```(?:json)?\s*", "", clean_content, flags=re.IGNORECASE)
                    clean_content = re.sub(r"\s*```$", "", clean_content)
                    clean_content = clean_content.strip()

            try:
                parsed = json.loads(clean_content)
            except Exception:
                start = clean_content.find("{")
                end = clean_content.rfind("}")
                if start != -1 and end != -1 and end > start:
                    sub = clean_content[start : end + 1]
                    # Strip trailing commas before closing braces/brackets
                    sub = re.sub(r",\s*([}\]])", r"\1", sub)
                    parsed = json.loads(sub)
                else:
                    raise

            if isinstance(parsed, dict) and "days" in parsed and len(parsed["days"]) > 0:
                # Ensure days_count and location are present
                parsed.setdefault("location", location)
                parsed.setdefault("days_count", days)
                parsed.setdefault("budget", budget)
                return parsed
        except Exception as exc:
            logger.warning("LLM itinerary generation failed (%s), using rich knowledge engine.", exc)

    return _generate_heuristic_itinerary(location, days, budget, interests)


if __name__ == "__main__":
    mcp.run()

