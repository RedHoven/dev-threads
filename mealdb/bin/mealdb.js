#!/usr/bin/env node

const https = require("https");
const { parseArgs } = require("util");

const BASE = "https://www.themealdb.com/api/json/v1/1";

// --- HTTP helper ---
function get(path) {
  return new Promise((resolve, reject) => {
    https.get(`${BASE}${path}`, (res) => {
      let data = "";
      res.on("data", (c) => (data += c));
      res.on("end", () => {
        try {
          resolve(JSON.parse(data));
        } catch {
          reject(new Error(`Failed to parse response from ${path}`));
        }
      });
      res.on("error", reject);
    }).on("error", reject);
  });
}

// --- Formatting helpers ---
function cyan(s) { return `\x1b[36m${s}\x1b[0m`; }
function bold(s) { return `\x1b[1m${s}\x1b[0m`; }
function dim(s) { return `\x1b[2m${s}\x1b[0m`; }
function yellow(s) { return `\x1b[33m${s}\x1b[0m`; }
function green(s) { return `\x1b[32m${s}\x1b[0m`; }

function printMealBrief(meal) {
  console.log(`  ${bold(meal.strMeal)} ${dim(`(${meal.strCategory || "?"} · ${meal.strArea || "?"})`)} ${dim(`[ID: ${meal.idMeal}]`)}`);
}

function printMealFull(meal) {
  console.log();
  console.log(bold("━".repeat(60)));
  console.log(bold(`  ${meal.strMeal}`));
  console.log(bold("━".repeat(60)));
  console.log(`  ${cyan("Category:")} ${meal.strCategory || "—"}`);
  console.log(`  ${cyan("Area:")}     ${meal.strArea || "—"}`);
  console.log(`  ${cyan("Tags:")}     ${meal.strTags || "—"}`);
  if (meal.strYoutube) {
    console.log(`  ${cyan("Video:")}    ${meal.strYoutube}`);
  }
  console.log();

  // Ingredients
  const ingredients = [];
  for (let i = 1; i <= 20; i++) {
    const ing = meal[`strIngredient${i}`];
    const meas = meal[`strMeasure${i}`];
    if (ing && ing.trim()) {
      ingredients.push({ ingredient: ing.trim(), measure: (meas || "").trim() });
    }
  }
  if (ingredients.length) {
    console.log(bold("  Ingredients:"));
    for (const { ingredient, measure } of ingredients) {
      console.log(`    ${green("•")} ${measure.padEnd(20)} ${ingredient}`);
    }
    console.log();
  }

  // Instructions
  if (meal.strInstructions) {
    console.log(bold("  Instructions:"));
    const lines = meal.strInstructions.split(/\r?\n/).filter(Boolean);
    for (const line of lines) {
      console.log(`    ${line}`);
    }
  }
  console.log();
}

// --- Commands ---
const commands = {
  search: {
    desc: "Search meals by name",
    usage: "mealdb search <query>",
    run: async (args) => {
      if (!args.length) return console.error("Usage: mealdb search <query>");
      const q = encodeURIComponent(args.join(" "));
      const data = await get(`/search.php?s=${q}`);
      if (!data.meals) return console.log("No meals found.");
      console.log(bold(`\n  Found ${data.meals.length} meal(s):\n`));
      data.meals.forEach(printMealBrief);
      console.log();
    },
  },

  letter: {
    desc: "List meals by first letter",
    usage: "mealdb letter <letter>",
    run: async (args) => {
      if (!args.length || args[0].length !== 1)
        return console.error("Usage: mealdb letter <a-z>");
      const data = await get(`/search.php?f=${args[0]}`);
      if (!data.meals) return console.log("No meals found.");
      console.log(bold(`\n  Meals starting with "${args[0].toUpperCase()}":\n`));
      data.meals.forEach(printMealBrief);
      console.log();
    },
  },

  get: {
    desc: "Get full meal details by ID",
    usage: "mealdb get <id>",
    run: async (args) => {
      if (!args.length) return console.error("Usage: mealdb get <id>");
      const data = await get(`/lookup.php?i=${args[0]}`);
      if (!data.meals) return console.log("Meal not found.");
      printMealFull(data.meals[0]);
    },
  },

  random: {
    desc: "Get a random meal",
    usage: "mealdb random",
    run: async () => {
      const data = await get("/random.php");
      if (!data.meals) return console.log("No meal returned.");
      printMealFull(data.meals[0]);
    },
  },

  categories: {
    desc: "List all meal categories",
    usage: "mealdb categories",
    run: async () => {
      const data = await get("/categories.php");
      if (!data.categories) return console.log("No categories found.");
      console.log(bold("\n  Categories:\n"));
      for (const cat of data.categories) {
        console.log(`  ${green("•")} ${bold(cat.strCategory.padEnd(15))} ${dim(cat.strCategoryDescription?.slice(0, 80) || "")}`);
      }
      console.log();
    },
  },

  filter: {
    desc: "Filter meals by ingredient, category, or area",
    usage: "mealdb filter --ingredient <name> | --category <name> | --area <name>",
    run: async (args) => {
      const { values } = parseArgs({
        args,
        options: {
          ingredient: { type: "string", short: "i" },
          category: { type: "string", short: "c" },
          area: { type: "string", short: "a" },
        },
        strict: true,
        allowPositionals: false,
      });

      let path;
      if (values.ingredient) {
        path = `/filter.php?i=${encodeURIComponent(values.ingredient)}`;
      } else if (values.category) {
        path = `/filter.php?c=${encodeURIComponent(values.category)}`;
      } else if (values.area) {
        path = `/filter.php?a=${encodeURIComponent(values.area)}`;
      } else {
        return console.error("Usage: mealdb filter -i <ingredient> | -c <category> | -a <area>");
      }

      const data = await get(path);
      if (!data.meals) return console.log("No meals found.");
      console.log(bold(`\n  ${data.meals.length} meal(s):\n`));
      data.meals.forEach(printMealBrief);
      console.log();
    },
  },

  list: {
    desc: "List all categories, areas, or ingredients",
    usage: "mealdb list <categories|areas|ingredients>",
    run: async (args) => {
      const type = (args[0] || "").toLowerCase();
      const map = {
        categories: "c",
        areas: "a",
        ingredients: "i",
        cats: "c",
        cuisines: "a",
        ing: "i",
      };
      if (!map[type]) return console.error("Usage: mealdb list <categories|areas|ingredients>");
      const data = await get(`/list.php?${map[type]}=list`);
      const key = Object.keys(data)[0];
      if (!data[key]) return console.log("No results.");
      console.log(bold(`\n  ${type.charAt(0).toUpperCase() + type.slice(1)}:\n`));
      for (const item of data[key]) {
        const val = Object.values(item)[0];
        console.log(`  ${green("•")} ${val}`);
      }
      console.log();
    },
  },

  help: {
    desc: "Show help",
    usage: "mealdb help [command]",
    run: (args) => {
      if (args[0] && commands[args[0]]) {
        const cmd = commands[args[0]];
        console.log(`\n  ${bold(args[0])} — ${cmd.desc}`);
        console.log(`  ${dim(cmd.usage)}\n`);
        return;
      }
      console.log(bold("\n  🍽️  mealdb — TheMealDB CLI\n"));
      console.log("  Usage: mealdb <command> [options]\n");
      console.log(bold("  Commands:\n"));
      for (const [name, cmd] of Object.entries(commands)) {
        if (name === "help") continue;
        console.log(`    ${green(name.padEnd(14))} ${cmd.desc}`);
      }
      console.log(`    ${green("help".padEnd(14))} Show help\n`);
      console.log(dim("  Examples:"));
      console.log(dim("    mealdb search pasta"));
      console.log(dim("    mealdb random"));
      console.log(dim("    mealdb get 52772"));
      console.log(dim("    mealdb filter -i chicken_breast"));
      console.log(dim("    mealdb filter -c Seafood"));
      console.log(dim("    mealdb list areas\n"));
    },
  },
};

// --- Main ---
const [,, cmd, ...args] = process.argv;

if (!cmd || cmd === "help") {
  commands.help.run(args);
} else if (commands[cmd]) {
  commands[cmd].run(args).catch((err) => {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  });
} else {
  console.error(`Unknown command: ${cmd}`);
  commands.help.run([]);
  process.exit(1);
}
