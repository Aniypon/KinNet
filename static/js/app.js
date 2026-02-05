/* Front-end glue: PWA registration, swipe gestures, confetti, onboarding tour. */

document.addEventListener("DOMContentLoaded", () => {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch((err) => console.warn("[KinNet] sw failed", err));
  }
  enableSwipeCards();
  if (window.location.search.includes("celebrate=1")) {
    fireConfetti();
  }
  maybeStartOnboarding();
});

/* --- Swipeable task cards --- */
function enableSwipeCards() {
  document.querySelectorAll(".swipe-card").forEach((card) => {
    const content = card.querySelector(".swipe-content");
    if (!content) return;
    let startX = null;
    let dx = 0;

    const reset = () => {
      content.style.transform = "translateX(0)";
      dx = 0;
      startX = null;
    };

    content.addEventListener("touchstart", (event) => {
      startX = event.touches[0].clientX;
    });
    content.addEventListener("touchmove", (event) => {
      if (startX == null) return;
      dx = event.touches[0].clientX - startX;
      content.style.transform = `translateX(${dx}px)`;
    });
    content.addEventListener("touchend", () => {
      const threshold = 90;
      if (dx > threshold && card.dataset.completeUrl) {
        window.location.href = card.dataset.completeUrl;
        return;
      }
      if (dx < -threshold && card.dataset.deleteUrl) {
        if (confirm("Удалить?")) {
          window.location.href = card.dataset.deleteUrl;
          return;
        }
      }
      reset();
    });
  });
}

/* --- Confetti microinteraction (lightweight, no deps) --- */
function fireConfetti() {
  const canvas = document.createElement("canvas");
  canvas.id = "confetti-canvas";
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const pieces = Array.from({ length: 120 }, () => ({
    x: Math.random() * canvas.width,
    y: -20,
    vy: 2 + Math.random() * 4,
    vx: (Math.random() - 0.5) * 4,
    rot: Math.random() * Math.PI,
    size: 6 + Math.random() * 6,
    color: `hsl(${Math.floor(Math.random() * 360)} 80% 60%)`,
  }));
  let frames = 0;
  const tick = () => {
    frames += 1;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    pieces.forEach((p) => {
      p.y += p.vy;
      p.x += p.vx;
      p.rot += 0.05;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size);
      ctx.restore();
    });
    if (frames < 220) requestAnimationFrame(tick);
    else canvas.remove();
  };
  tick();
}

/* --- Walkthrough using Shepherd.js (loaded from CDN in base.html) --- */
function maybeStartOnboarding() {
  const root = document.getElementById("kinnet-root");
  if (!root) return;
  if (root.dataset.onboarding !== "1") return;
  if (typeof window.Shepherd === "undefined") return;
  if (localStorage.getItem("kinnet:onboarded") === "1") return;

  const tour = new window.Shepherd.Tour({
    defaultStepOptions: { scrollTo: true, cancelIcon: { enabled: true } },
  });
  tour.addStep({
    id: "welcome",
    text: "Добро пожаловать в KinNet! Здесь живут события, задачи и история вашей семьи.",
    buttons: [{ text: "Дальше", action: tour.next }],
  });
  tour.addStep({
    id: "menu",
    attachTo: { element: ".bottom-nav", on: "top" },
    text: "Внизу — главное меню. На телефоне можно установить как приложение.",
    buttons: [{ text: "Дальше", action: tour.next }],
  });
  tour.addStep({
    id: "elder",
    attachTo: { element: '[data-tour="elder"]', on: "left" },
    text: "Этот переключатель включает крупный шрифт и высокий контраст для родителей и бабушек/дедушек.",
    buttons: [
      {
        text: "Готово",
        action: () => {
          localStorage.setItem("kinnet:onboarded", "1");
          tour.complete();
        },
      },
    ],
  });
  tour.start();
}

window.KinNet = { fireConfetti };
