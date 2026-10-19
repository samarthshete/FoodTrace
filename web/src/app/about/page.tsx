import { PRODUCT_NAME, PRODUCT_TAGLINE } from "@/lib/brand";

export const metadata = { title: "About" };

const SOURCES = [
  { name: "Open Food Facts", url: "https://world.openfoodfacts.org", what: "Products, ingredients, nutrition, NOVA groups, and EFSA additive evaluations (via its additives taxonomy)", license: "Open Database License (ODbL)" },
  { name: "USDA FoodData Central", url: "https://fdc.nal.usda.gov", what: "Branded food nutrition for US products", license: "Public domain (CC0)" },
  { name: "openFDA", url: "https://open.fda.gov", what: "Food recall records", license: "Public domain" },
  { name: "FDA Substances Added to Food", url: "https://www.hfpappexternal.fda.gov/scripts/fdcc/?set=FoodSubstances", what: "US regulatory status of additives", license: "US government work" },
  { name: "Nutri-Score (2023 algorithm)", url: "https://www.santepubliquefrance.fr/en/nutri-score", what: "The nutrition part of the score", license: "Published algorithm, reimplemented" },
];

// METH-6: what this is, and credit for every data source.
export default function AboutPage() {
  return (
    <article className="flex flex-col gap-4 text-sm leading-6">
      <h1 className="text-2xl font-bold">About</h1>
      <p>
        <strong>{PRODUCT_NAME}</strong> — {PRODUCT_TAGLINE} — scores US grocery products from 0 to
        100, with every point linked to the rule and source behind it. It&apos;s
        educational information, not medical advice: for health decisions, talk to a doctor or
        dietitian.
      </p>
      <p>
        No AI decides the score. It comes from published rules applied the same way every time, and
        the scoring version is shown on every product.
      </p>
      <h2 className="text-lg font-semibold">Data sources</h2>
      <ul className="flex flex-col gap-3">
        {SOURCES.map((s) => (
          <li key={s.name}>
            <a className="font-medium underline" href={s.url}>
              {s.name}
            </a>
            <br />
            {s.what}. <span className="text-zinc-600">License: {s.license}.</span>
          </li>
        ))}
      </ul>
      <p>
        Product data comes from Open Food Facts contributors. If something is wrong, it can be
        corrected on Open Food Facts, which helps everyone.
      </p>
      <h2 className="text-lg font-semibold">Open source</h2>
      <p>
        The code is MIT-licensed:{" "}
        <a className="underline" href="https://github.com/samarthshete/FoodTrace">
          {PRODUCT_NAME} on GitHub
        </a>
        .
      </p>
    </article>
  );
}
