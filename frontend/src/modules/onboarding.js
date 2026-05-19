import Shepherd from "shepherd.js";

export function maybeStartOnboarding() {
  const root = document.getElementById("kinnet-root");
  if (!root || root.dataset.onboarding !== "1" || localStorage.getItem("kinnet:onboarded") === "1") return;

  const tour = new Shepherd.Tour({
    defaultStepOptions: { scrollTo: true, cancelIcon: { enabled: true } },
  });
  const markDone = () => localStorage.setItem("kinnet:onboarded", "1");
  tour.on("cancel", markDone);
  tour.on("complete", markDone);
  tour.addStep({
    id: "welcome",
    text: "KinNet собирает семейные дела, даты и заботу в одном месте.",
    buttons: [{ text: "Дальше", action: tour.next }],
  });
  tour.addStep({
    id: "menu",
    attachTo: { element: window.matchMedia("(max-width: 1020px)").matches ? ".bottom-nav" : ".side-nav", on: window.matchMedia("(max-width: 1020px)").matches ? "top" : "right" },
    text: "Здесь быстрый доступ к главным семейным сценариям.",
    buttons: [{ text: "Дальше", action: tour.next }],
  });
  tour.addStep({
    id: "elder",
    attachTo: { element: '[data-tour="elder"]', on: "left" },
    text: "Крупный режим делает интерфейс спокойнее для старшего поколения.",
    buttons: [
      {
        text: "Готово",
        action: () => {
          markDone();
          tour.complete();
        },
      },
    ],
  });
  tour.start();
}
