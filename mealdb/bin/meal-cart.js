#!/usr/bin/env node

/**
 * meal-cart.js — Fetch a recipe from TheMealDB → search Picnic → build cart
 * Usage: node meal-cart.js <meal-id> [--people <n>] [--dry-run] [--add-to-cart]
 * Env: PICNIC_EMAIL, PICNIC_PASSWORD
 */

const https = require("https");
const PicnicClient = require("picnic-api");

const MEALDB_BASE = "https://www.themealdb.com/api/json/v1/1";

function get(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => {
        try { resolve(JSON.parse(data)); } catch { reject(new Error("JSON parse error")); }
      });
    }).on("error", reject);
  });
}

function cyan(s) { return `\x1b[36m${s}\x1b[0m`; }
function bold(s) { return `\x1b[1m${s}\x1b[0m`; }
function dim(s) { return `\x1b[2m${s}\x1b[0m`; }
function green(s) { return `\x1b[32m${s}\x1b[0m`; }
function yellow(s) { return `\x1b[33m${s}\x1b[0m`; }
function red(s) { return `\x1b[31m${s}\x1b[0m`; }

function evalFraction(s) {
  if (!s) return 1;
  if (s.includes("/")) {
    const [n, d] = s.split("/").map(Number);
    return n / d;
  }
  return parseFloat(s) || 1;
}

function parseMeasure(raw) {
  if (!raw) return null;
  const s = raw.trim();

  const vague = /^(to taste|to serve|handful|sprinkling|pinch|drizzle|dash|bunch)/i;
  if (vague.test(s)) return { value: 1, unit: "count", raw: s, vague: true };

  const juiceMatch = s.match(/^Juice of (\d+)/i);
  if (juiceMatch) return { value: parseInt(juiceMatch[1]), unit: "count", raw: s };

  const patterns = [
    { re: /^([\d./]+)\s*(kg|g|mg)\b/i, unit: "g", mult: { kg: 1000, g: 1, mg: 0.001 } },
    { re: /^([\d./]+)\s*(l|ml|litre|liter)\b/i, unit: "ml", mult: { l: 1000, ml: 1, litre: 1000, liter: 1000 } },
    { re: /^([\d./]+)\s*(lb|lbs|pound|pounds)\b/i, unit: "g", mult: { lb: 453.6, lbs: 453.6, pound: 453.6, pounds: 453.6 } },
    { re: /^([\d./]+)\s*(oz|ounce|ounces)\b/i, unit: "g", mult: { oz: 28.35, ounce: 28.35, ounces: 28.35 } },
    { re: /^([\d./]+)\s*(cup|cups)\b/i, unit: "count", mult: { cup: 1, cups: 1 } },
    { re: /^([\d./]+)\s*(tsp|teaspoon|teaspoons)\b/i, unit: "count", mult: { tsp: 1, teaspoon: 1, teaspoons: 1 } },
    { re: /^([\d./]+)\s*(tblsp|tbsp|tablespoon|tablespoons)\b/i, unit: "count", mult: { tblsp: 1, tbsp: 1, tablespoon: 1, tablespoons: 1 } },
  ];

  for (const { re, unit, mult } of patterns) {
    const m = s.match(re);
    if (m) {
      const num = evalFraction(m[1]);
      const u = m[2].toLowerCase();
      return { value: Math.round(num * (mult[u] || 1)), unit, raw: s };
    }
  }

  const countMatch = s.match(/^([\d./]+)/);
  if (countMatch) {
    return { value: evalFraction(countMatch[1]), unit: "count", raw: s };
  }

  return { value: 1, unit: "count", raw: s, vague: true };
}

function extractIngredients(meal) {
  const ingredients = [];
  for (let i = 1; i <= 20; i++) {
    const ing = meal[`strIngredient${i}`];
    const meas = meal[`strMeasure${i}`];
    if (ing && ing.trim()) {
      ingredients.push({
        name: ing.trim(),
        measure: parseMeasure(meas),
        searchQuery: ing.trim().toLowerCase(),
      });
    }
  }
  return ingredients;
}

function scaleIngredients(ingredients, scaleFactor) {
  return ingredients.map((ing) => ({
    ...ing,
    measure: ing.measure ? { ...ing.measure, value: Math.ceil(ing.measure.value * scaleFactor) } : ing.measure,
    quantity: Math.max(1, Math.ceil((ing.measure?.value || 1) * scaleFactor / 1)),
  }));
}

async function searchPicnic(client, query) {
  try {
    const results = await client.catalog.search(query);
    if (!results || !results.length) return null;
    // Return top 3 for user to pick from
    return results.slice(0, 3);
  } catch (err) {
    return { error: err.message };
  }
}

function formatPrice(cents) {
  if (!cents && cents !== 0) return "price unknown";
  return `€${(cents / 100).toFixed(2)}`;
}

async function main() {
  const args = process.argv.slice(2);
  const mealId = args.find((a) => /^\d+$/.test(a));
  const peopleIdx = args.indexOf("--people");
  const people = peopleIdx !== -1 ? parseInt(args[peopleIdx + 1]) || 4 : 4;
  const dryRun = args.includes("--dry-run");
  const addToCart = args.includes("--add-to-cart");

  if (!mealId) {
    console.log(`${bold("🍽️  meal-cart")} — Recipe → Picnic Shopping Cart\n`);
    console.log("Usage: node meal-cart.js <meal-id> [--people <n>] [--dry-run] [--add-to-cart]\n");
    process.exit(0);
  }

  // 1. Fetch recipe
  console.log(dim("Fetching recipe from TheMealDB..."));
  const data = await get(`${MEALDB_BASE}/lookup.php?i=${mealId}`);
  if (!data.meals) { console.error(red("Meal not found.")); process.exit(1); }

  const meal = data.meals[0];
  console.log();
  console.log(bold("━".repeat(60)));
  console.log(bold(`  🍽️  ${meal.strMeal}`));
  console.log(bold("━".repeat(60)));
  console.log(`  ${cyan("Category:")} ${meal.strCategory}`);
  console.log(`  ${cyan("Area:")}     ${meal.strArea}`);
  console.log(`  ${cyan("Servings:")} ${people} people`);
  console.log();

  // 2. Extract & scale
  const baseIngredients = extractIngredients(meal);
  const scaleFactor = people / 2;
  const ingredients = scaleIngredients(baseIngredients, scaleFactor);

  console.log(bold("  📋 Ingredients:"));
  for (const ing of ingredients) {
    const qty = ing.measure ? `${ing.measure.value} ${ing.measure.unit}` : "?";
    console.log(`    ${green("•")} ${qty.padEnd(16)} ${ing.name}${ing.measure?.vague ? yellow(" (add to taste)") : ""}`);
  }
  console.log();

  if (dryRun) {
    console.log(dim("  Dry run — exiting. Remove --dry-run to connect to Picnic."));
    return;
  }

  // 3. Picnic login
  const email = process.env.PICNIC_EMAIL;
  const password = process.env.PICNIC_PASSWORD;
  if (!email || !password) {
    console.error(red("Set PICNIC_EMAIL and PICNIC_PASSWORD (or use --dry-run)"));
    process.exit(1);
  }

  console.log(dim("Connecting to Picnic..."));
  const client = new PicnicClient({ countryCode: "NL" });
  try {
    await client.auth.login(email, password);
    console.log(green("✓ Authenticated with Picnic\n"));
  } catch (err) {
    console.error(red(`Login failed: ${err.message}`));
    process.exit(1);
  }

  // 4. Search for each ingredient — show top candidates
  console.log(bold("  🔍 Searching Picnic for products...\n"));

  const selections = []; // { ingredient, candidates, chosen }
  const unmatched = [];

  for (const ing of ingredients) {
    if (ing.measure?.vague) {
      console.log(`    ${yellow("⏭")}  ${bold(ing.name)} — ${dim("skipping (vague measure)")}`);
      continue;
    }

    process.stdout.write(`    Searching: ${bold(ing.name)}... `);
    const candidates = await searchPicnic(client, ing.searchQuery);

    if (!candidates || candidates.error) {
      console.log(red("no match"));
      unmatched.push(ing.name);
      await new Promise((r) => setTimeout(r, 300));
      continue;
    }

    console.log(green(`${candidates.length} product(s) found`));
    selections.push({ ingredient: ing, candidates, chosen: candidates[0] });

    for (let i = 0; i < candidates.length; i++) {
      const c = candidates[i];
      const marker = i === 0 ? green("●") : dim("○");
      const price = c.price ? formatPrice(c.price) : "—";
      const unit = c.unit_quantity ? dim(` (${c.unit_quantity}${c.display_volume ? " " + c.display_volume : ""})`) : "";
      console.log(`      ${marker} ${bold(c.name)} ${unit} — ${price} ${i === 0 ? green("← best match") : ""}`);
    }
    console.log();

    await new Promise((r) => setTimeout(r, 300));
  }

  // 5. Summary & cost
  let estimatedTotal = 0;
  console.log(bold("  🛒 Proposed Cart:\n"));
  console.log(`    ${bold("Ingredient".padEnd(24))} ${bold("Product".padEnd(40))} ${bold("Qty")}  ${bold("Price")}`);
  console.log(`    ${"─".repeat(24)} ${"─".repeat(40)} ${"─".repeat(4)} ${"─".repeat(8)}`);

  for (const sel of selections) {
    const p = sel.chosen;
    const price = p.price || 0;
    estimatedTotal += price / 100;
    console.log(
      `    ${sel.ingredient.name.padEnd(24)} ${p.name.substring(0, 40).padEnd(40)} ${String(sel.ingredient.quantity).padEnd(4)} ${formatPrice(price)}`
    );
  }

  if (unmatched.length) {
    console.log();
    console.log(yellow("  ⚠ Not found on Picnic (buy manually):"));
    for (const u of unmatched) console.log(`    • ${u}`);
  }

  console.log();
  console.log(bold("  💰 Cost Estimate:"));
  console.log(`    ${cyan("Subtotal:")} €${estimatedTotal.toFixed(2)}`);
  console.log(`    ${cyan("Budget:")}   €50.00`);
  const within = estimatedTotal <= 50;
  console.log(`    ${cyan("Status:")}   ${within ? green("✓ Within budget") : red("✗ Over budget by €" + (estimatedTotal - 50).toFixed(2))}`);
  console.log();

  // 6. Confirm & add to cart
  if (addToCart) {
    console.log(bold("  Adding to cart...\n"));
    for (const sel of selections) {
      try {
        await client.cart.addProductToCart(sel.chosen.id, sel.ingredient.quantity || 1);
        console.log(`    ${green("✓")} ${sel.chosen.name} ×${sel.ingredient.quantity || 1}`);
      } catch (err) {
        console.log(`    ${red("✗")} ${sel.chosen.name}: ${err.message}`);
      }
      await new Promise((r) => setTimeout(r, 200));
    }
    console.log(green("\n  ✓ Done! Check your Picnic app."));
  } else {
    console.log(bold("  ➡️  Next step: Run with --add-to-cart to add these to your Picnic cart."));
    console.log(dim("     Or tell me to change any product picks before adding."));
  }

  // 7. JSON
  console.log();
  console.log(dim("  📦 JSON:"));
  const payload = {
    recipe: { name: meal.strMeal, id: meal.idMeal },
    servings: people,
    shopping_list: selections.map((s) => ({
      ingredient: s.ingredient.name,
      amount: s.ingredient.measure,
      picnic: {
        id: s.chosen.id,
        name: s.chosen.name,
        price_cents: s.chosen.price,
        quantity: s.ingredient.quantity || 1,
      },
      alternatives: s.candidates.slice(1).map((c) => ({ id: c.id, name: c.name, price_cents: c.price })),
    })),
    cost_estimate: { subtotal: Math.round(estimatedTotal * 100) / 100, currency: "EUR", within_budget: within },
    unmatched,
  };
  console.log(JSON.stringify(payload, null, 2));
}

main().catch((err) => {
  console.error(red(`Error: ${err.message}`));
  process.exit(1);
});
