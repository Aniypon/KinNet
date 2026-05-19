import { createIcons } from "lucide";
import { icons } from "./icons.js";

export function enableIngredientBuilders() {
  document.querySelectorAll("[data-ingredient-builder]").forEach((builder) => {
    const source = builder.querySelector("[data-ingredient-source]");
    const rows = builder.querySelector("[data-ingredient-rows]");
    const addButton = builder.querySelector("[data-add-ingredient]");
    const form = builder.closest("form");
    if (!source || !rows || !addButton || !form) return;

    const parseLine = (line) => {
      const [name = "", quantity = "", unit = ""] = line.split("|").map((part) => part.trim());
      return { name, quantity, unit };
    };

    const createRow = (ingredient = {}) => {
      const row = document.createElement("div");
      row.className = "ingredient-row";
      row.innerHTML = `
        <input data-ingredient-name type="text" autocomplete="off" placeholder="Например: огурцы" aria-label="Продукт" value="${escapeAttribute(ingredient.name || "")}">
        <input data-ingredient-quantity type="text" inputmode="decimal" autocomplete="off" placeholder="4" aria-label="Количество" value="${escapeAttribute(ingredient.quantity || "")}">
        <input data-ingredient-unit type="text" autocomplete="off" placeholder="шт" aria-label="Единица измерения" value="${escapeAttribute(ingredient.unit || "")}">
        <button class="icon-button ingredient-row__remove" type="button" aria-label="Удалить продукт">
          <i data-lucide="x"></i>
        </button>
      `;
      rows.append(row);
      row.querySelector(".ingredient-row__remove")?.addEventListener("click", () => {
        row.remove();
        if (!rows.children.length) createRow();
        syncSource();
      });
      row.querySelectorAll("input").forEach((input) => input.addEventListener("input", syncSource));
      createIcons({ icons, attrs: { "stroke-width": 1.8 } });
      return row;
    };

    const syncSource = () => {
      source.value = [...rows.querySelectorAll(".ingredient-row")]
        .map((row) => {
          const name = row.querySelector("[data-ingredient-name]")?.value.trim() || "";
          const quantity = row.querySelector("[data-ingredient-quantity]")?.value.trim() || "";
          const unit = row.querySelector("[data-ingredient-unit]")?.value.trim() || "";
          if (!name && !quantity && !unit) return "";
          return [name, quantity, unit].join(" | ");
        })
        .filter(Boolean)
        .join("\n");
    };

    const initialIngredients = source.value
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map(parseLine);

    (initialIngredients.length ? initialIngredients : [{}]).forEach(createRow);
    addButton.addEventListener("click", () => {
      const row = createRow();
      row.querySelector("input")?.focus();
      syncSource();
    });
    form.addEventListener("submit", syncSource);
  });
}

function escapeAttribute(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
