export function enableReveal() {
  const elements = document.querySelectorAll("[data-reveal]");
  if (!elements.length) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    elements.forEach((element) => element.classList.add("is-visible"));
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.12 }
  );
  elements.forEach((element, index) => {
    element.style.setProperty("--reveal-delay", `${Math.min(index * 55, 440)}ms`);
    observer.observe(element);
  });
}

export function enableParallax() {
  const layers = document.querySelectorAll("[data-parallax]");
  if (!layers.length || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  let ticking = false;
  const update = () => {
    const y = window.scrollY;
    layers.forEach((layer) => {
      const depth = Number(layer.dataset.parallax || "0.08");
      layer.style.transform = `translate3d(0, ${Math.round(y * depth)}px, 0)`;
    });
    ticking = false;
  };
  window.addEventListener(
    "scroll",
    () => {
      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    },
    { passive: true }
  );
  update();
}

export function enablePointerGlow() {
  const targets = document.querySelectorAll(".surface, .module-card, .home-hero, .page-hero");
  targets.forEach((target) => {
    target.addEventListener("pointermove", (event) => {
      const rect = target.getBoundingClientRect();
      target.style.setProperty("--pointer-x", `${event.clientX - rect.left}px`);
      target.style.setProperty("--pointer-y", `${event.clientY - rect.top}px`);
    });
  });
}

export function enableSwipeCards() {
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
      if (dx < -threshold && card.dataset.deleteUrl && confirm("Удалить?")) {
        window.location.href = card.dataset.deleteUrl;
        return;
      }
      reset();
    });
  });
}

export function fireConfetti() {
  const canvas = document.createElement("canvas");
  canvas.id = "confetti-canvas";
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");
  const pieces = Array.from({ length: 140 }, () => ({
    x: Math.random() * canvas.width,
    y: -20,
    vy: 2 + Math.random() * 4,
    vx: (Math.random() - 0.5) * 4,
    rot: Math.random() * Math.PI,
    size: 6 + Math.random() * 8,
    color: ["#c8684b", "#f3b85b", "#809978", "#e6a6a0", "#7f5539"][Math.floor(Math.random() * 5)],
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
