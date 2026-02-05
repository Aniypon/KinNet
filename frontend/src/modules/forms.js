import { showToast } from "./toast.js";

export function enableFormDrafts() {
  document.querySelectorAll("form").forEach((form) => {
    if (form.method?.toLowerCase() !== "post" || form.id === "chat-composer" || form.dataset.noDraft === "1") return;
    const fields = [...form.querySelectorAll("input, textarea, select")].filter((field) => {
      const type = field.getAttribute("type");
      return field.name && !["hidden", "password", "file", "submit", "button"].includes(type || "");
    });
    if (!fields.length) return;
    const key = `kinnet:draft:${location.pathname}:${form.action || "local"}:${fields.map((field) => field.name).join(",")}`;
    try {
      const saved = JSON.parse(localStorage.getItem(key) || "{}");
      fields.forEach((field) => {
        if (saved[field.name] && !field.value) field.value = saved[field.name];
      });
    } catch {
      // Ignore broken local drafts.
    }
    const persist = () => {
      const payload = {};
      fields.forEach((field) => {
        if (field.type === "checkbox") payload[field.name] = field.checked;
        else payload[field.name] = field.value;
      });
      localStorage.setItem(key, JSON.stringify(payload));
    };
    fields.forEach((field) => field.addEventListener("input", persist));
    form.addEventListener("submit", () => localStorage.removeItem(key));
  });
}

export function enableSmartInputs() {
  document.querySelectorAll('input[name*="phone"], input[type="tel"]').forEach((input) => {
    input.setAttribute("inputmode", "tel");
    input.placeholder ||= "+7 999 123-45-67";
    input.addEventListener("input", () => {
      let digits = input.value.replace(/\D/g, "");
      if (digits.startsWith("8")) digits = `7${digits.slice(1)}`;
      if (digits.startsWith("7")) {
        const parts = [digits.slice(0, 1), digits.slice(1, 4), digits.slice(4, 7), digits.slice(7, 9), digits.slice(9, 11)].filter(Boolean);
        input.value = `+${parts[0]}${parts[1] ? ` ${parts[1]}` : ""}${parts[2] ? ` ${parts[2]}` : ""}${parts[3] ? `-${parts[3]}` : ""}${parts[4] ? `-${parts[4]}` : ""}`;
      }
    });
  });
  document.querySelectorAll('input[name*="address"]').forEach((input) => {
    input.setAttribute("autocomplete", "street-address");
    input.placeholder ||= "Город, улица, дом, подъезд";
  });
  document.querySelectorAll('input[type="date"]').forEach((input) => {
    input.setAttribute("max", input.name.includes("birth") ? new Date().toISOString().slice(0, 10) : "9999-12-31");
  });
}

export function enableQuickForms() {
  document.body.addEventListener("htmx:afterRequest", (event) => {
    const form = event.detail?.elt;
    if (!form?.matches?.("[data-quick-form]")) return;
    if (!event.detail.successful) {
      showToast("Не удалось сохранить. Проверьте поля.", "error");
      return;
    }
    let message = "Сохранено";
    try {
      const data = JSON.parse(event.detail.xhr.responseText || "{}");
      message = data.message || message;
    } catch {
      // Non-JSON responses still count as saved if HTMX reports success.
    }
    form.reset();
    showToast(message);
    if (form.dataset.refresh === "1") {
      window.setTimeout(() => window.location.reload(), 520);
    }
  });
}
