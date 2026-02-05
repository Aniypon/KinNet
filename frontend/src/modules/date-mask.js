const DATE_DIGITS = 8;
const DATETIME_DIGITS = 12;

function formatDate(d) {
  if (d.length <= 2) return d;
  if (d.length <= 4) return `${d.slice(0, 2)}.${d.slice(2)}`;
  return `${d.slice(0, 2)}.${d.slice(2, 4)}.${d.slice(4, 8)}`;
}

function formatDateTime(d) {
  if (d.length <= 8) return formatDate(d);
  const base = formatDate(d.slice(0, 8));
  if (d.length <= 10) return `${base} ${d.slice(8)}`;
  return `${base} ${d.slice(8, 10)}:${d.slice(10, 12)}`;
}

function attach(input, kind) {
  if (input.dataset.maskBound === "1") return;
  input.dataset.maskBound = "1";
  const maxDigits = kind === "datetime" ? DATETIME_DIGITS : DATE_DIGITS;
  input.setAttribute("type", "text");
  input.setAttribute("inputmode", "numeric");
  input.setAttribute("autocomplete", "off");
  if (!input.placeholder) {
    input.placeholder = kind === "datetime" ? "дд.мм.гггг чч:мм" : "дд.мм.гггг";
  }

  const reformat = () => {
    const digits = input.value.replace(/\D/g, "").slice(0, maxDigits);
    input.value = kind === "datetime" ? formatDateTime(digits) : formatDate(digits);
  };

  input.addEventListener("input", reformat);
  input.addEventListener("blur", reformat);
  if (input.value) reformat();
}

export function enableDateMask(root = document) {
  root.querySelectorAll('input[data-mask="date"]').forEach((el) => attach(el, "date"));
  root.querySelectorAll('input[data-mask="datetime"]').forEach((el) => attach(el, "datetime"));
}
