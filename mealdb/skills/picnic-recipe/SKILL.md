---
name: openclaw-picnic-recipe-skill
description: "Use when the user asks to build or solve a grocery and meal-planning challenge with Picnic API and TheMealDB. Produces a practical plan, ingredient matching, and cart-ready outputs."
---

# OpenClaw Skill: Picnic + Recipe API Challenge

## Challenge Summary
Build an agent workflow that creates a meal plan and shopping list by combining:
- Picnic product data (`picnic-api`)
- Recipe data from TheMealDB API (`https://www.themealdb.com/api.php`)

The agent must translate recipe ingredients into purchasable Picnic products and return a clear, actionable result.

## Goal
Given user constraints (diet, budget, household size, cooking time), generate:
1. A multi-day recipe plan.
2. A normalized ingredient list.
3. A mapped Picnic shopping list (with product IDs when available).
4. A cost estimate and substitutions for missing items.

## Inputs
The agent should collect these values before execution:
- days: number of days to plan.
- people: number of servings per meal.
- meals_per_day: breakfast/lunch/dinner count.
- diet: optional (vegan, vegetarian, pescatarian, etc.).
- allergies: optional exclusion list.
- max_budget: optional currency budget.
- country or locale: for product availability.
- themealdb_base_url: default https://www.themealdb.com/api/json/v1/1.

## Required Environment
- Picnic credentials/config for picnic-api.
- TheMealDB access configuration (free tier usually needs no API key).
- Optional currency conversion source if recipe and grocery pricing use different currencies.

## Workflow
1. Validate required inputs and ask for missing constraints.
2. Fetch candidate recipes from TheMealDB API.
3. Filter recipes by diet, allergies, prep time, and servings.
4. Normalize ingredients into canonical units (g, ml, count).
5. Query picnic-api to find best matching products per ingredient.
6. Rank matches by relevance, price-per-unit, and package fit.
7. Propose substitutions when exact matches are unavailable.
8. Build an aggregated shopping cart list and estimate total cost.
9. Return final response in both human-readable and machine-readable forms.

## Output Contract
Return two sections:

### 1) Human Summary
- Meal plan by day.
- Missing or ambiguous ingredient mappings.
- Total estimated cost vs. budget.
- Suggested substitutions and tradeoffs.

### 2) JSON Payload

{
  "plan": [
    {
      "day": 1,
      "meals": [
        {
          "name": "Recipe name",
          "recipe_id": "themealdb-idMeal",
          "servings": 2
        }
      ]
    }
  ],
  "shopping_list": [
    {
      "ingredient": "tomato",
      "normalized_amount": {
        "value": 400,
        "unit": "g"
      },
      "picnic_match": {
        "product_id": "12345",
        "name": "Picnic Product Name",
        "quantity": 2,
        "unit_price": 1.99,
        "currency": "EUR"
      },
      "confidence": 0.92,
      "alternatives": []
    }
  ],
  "cost_estimate": {
    "subtotal": 42.75,
    "currency": "EUR",
    "within_budget": true
  },
  "unmatched_ingredients": []
}

## Rules
- Never fabricate API responses, product IDs, or prices.
- If an API call fails, provide partial results and clearly mark failed steps.
- Keep ingredient-unit conversions explicit and traceable.
- Respect user allergy exclusions as hard constraints.
- If budget cannot be met, return a cheaper fallback plan.
- Use real TheMealDB fields (`strIngredient1..20`, `strMeasure1..20`, `idMeal`, `strMeal`).

## Suggested Tooling Notes
- Use deterministic normalization helpers for unit conversion.
- Cache product lookups to reduce repeated picnic-api calls.
- Keep TheMealDB API calls isolated in a dedicated module for maintainability.
- Log per-ingredient match confidence to support debugging.

## Example Prompt
"Plan 5 days of vegetarian dinners for 2 people under 60 EUR using Picnic products. Use TheMealDB (`https://www.themealdb.com/api.php`) for recipes, exclude peanuts, and output both a readable summary and the JSON contract."

## Evaluation Criteria
- Mapping quality: ingredient to product match precision.
- Practicality: meals are cookable with returned products.
- Cost control: plan remains within budget when possible.
- Robustness: clear handling of missing data and API failures.
- Explainability: substitutions and assumptions are explicit.
