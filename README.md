# picky

**From recipe to shopping cart in one conversation.**

Picky combines [TheMealDB](https://www.themealdb.com/api.php) recipes with [Picnic](https://picnic.app) grocery delivery — search for meals, pick what you want, and have the ingredients added to your Picnic cart automatically.

```
"I want to cook dinner for 4 tonight"  →  🍽️ Recipe  →  🛒 Picnic Cart  →  📦 Order
```

---

## What's inside

```
picky/
├── mealdb/                    # Node.js CLI tools
│   ├── bin/
│   │   ├── mealdb.js          # TheMealDB recipe browser
│   │   └── meal-cart.js       # Recipe → Picnic cart pipeline
│   ├── package.json
│   └── skills/                # OpenClaw agent skills
│       ├── meal-planner/      # Full conversational meal planning flow
│       └── picnic-recipe/     # Picnic + TheMealDB integration spec
└── src/dev_threads/           # Python VM orchestration (existing)
```

---

## Quick start

### Install the CLI

```bash
cd mealdb
npm install
npm link    # makes `mealdb` available globally
```

### Browse recipes

```bash
# Search by name
mealdb search pasta

# Get full recipe with ingredients & instructions
mealdb get 52772

# Random meal — surprise me
mealdb random

# Filter by category, cuisine, or ingredient
mealdb filter -c Chicken
mealdb filter -a Italian
mealdb filter -i salmon

# List available categories, areas, ingredients
mealdb list categories
mealdb list areas
mealdb list ingredients
```

### Build a Picnic shopping cart

```bash
# Dry run — see what would be searched
node mealdb/bin/meal-cart.js 53161 --people 4 --dry-run

# Live — search Picnic and show matches
PICNIC_EMAIL=you@example.com PICNIC_PASSWORD=secret \
  node mealdb/bin/meal-cart.js 53161 --people 4

# Full send — search + add to your cart
PICNIC_EMAIL=you@example.com PICNIC_PASSWORD=secret \
  node mealdb/bin/meal-cart.js 53161 --people 4 --add-to-cart
```

**Note:** Picnic requires SMS 2FA verification on first login. The tool will prompt you for the code.

---

## How it works

### 1. Search recipes
The `mealdb` CLI wraps the free [TheMealDB API](https://www.themealdb.com/api.php). Search by name, filter by category/cuisine/ingredient, or get a random meal. Full recipe details include ingredients, quantities, and step-by-step instructions.

### 2. Normalize ingredients
`meal-cart.js` parses the raw TheMealDB ingredient data (`strIngredient1..20`, `strMeasure1..20`) and normalizes quantities into canonical units (grams, milliliters, count). It scales proportions based on servings.

### 3. Match to Picnic products
Each ingredient is searched against Picnic's catalog using their API. The tool shows the best match plus alternatives, so you can swap if needed.

### 4. Add to cart
With `--add-to-cart`, products are added directly to your Picnic cart. Open the app to review and place your order.

### 5. Output
Every run produces a structured JSON payload:

```json
{
  "recipe": { "name": "Chicken & chorizo rice pot", "id": "53161" },
  "cart": [
    {
      "ingredient": "Chicken",
      "product_id": "s1014735",
      "product_name": "'t Slagershuys kipfilets",
      "quantity": 1
    }
  ],
  "total_eur": 28.50,
  "unmatched": []
}
```

---

## CLI reference

### `mealdb`

| Command | Description |
|---|---|
| `mealdb search <query>` | Search meals by name |
| `mealdb get <id>` | Full recipe details by ID |
| `mealdb random` | Random meal |
| `mealdb letter <a-z>` | Browse by first letter |
| `mealdb categories` | List all categories |
| `mealdb filter -i <ingredient>` | Filter by ingredient |
| `mealdb filter -c <category>` | Filter by category (e.g. Seafood) |
| `mealdb filter -a <area>` | Filter by cuisine (e.g. Italian) |
| `mealdb list areas\|categories\|ingredients` | Browse filters |
| `mealdb help [command]` | Show help |

### `meal-cart.js`

| Flag | Description |
|---|---|
| `<meal-id>` | TheMealDB recipe ID (required) |
| `--people <n>` | Number of servings (default: 4) |
| `--dry-run` | Show what would be searched (no Picnic auth needed) |
| `--add-to-cart` | Add matched products to your Picnic cart |

**Environment variables:**
- `PICNIC_EMAIL` — your Picnic account email
- `PICNIC_PASSWORD` — your Picnic account password

---

## Agent skills

Picky includes two [OpenClaw](https://github.com/openclaw/openclaw) agent skills:

### `meal-planner`
A conversational flow for the full recipe-to-cart pipeline. Handles clarification questions, recipe search, user selection, Picnic product matching, 2FA auth, and cart management.

### `picnic-recipe`
A structured specification for building meal plans that combine Picnic product data with TheMealDB recipes. Includes input/output contracts, normalization rules, and evaluation criteria.

To use with OpenClaw, copy the `skills/` directory to your workspace.

---

## Dependencies

- **Node.js** ≥ 18
- **TheMealDB API** — free, no API key needed (test key `1`)
- **Picnic account** — for shopping cart features ([picnic.app](https://picnic.app))
- **picnic-api** — npm package ([github.com/MRVDH/picnic-api](https://github.com/MRVDH/picnic-api))

---

## Development

```bash
cd mealdb
npm install

# Test mealdb CLI
mealdb search chicken

# Test cart pipeline (dry run)
node bin/meal-cart.js 53161 --people 4 --dry-run
```

---

## License

MIT
