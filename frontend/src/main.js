import Alpine from "alpinejs";
import htmx from "htmx.org";
import Shepherd from "shepherd.js";
import "shepherd.js/dist/css/shepherd.css";
import { createIcons } from "lucide";
import "./styles.css";

import { icons } from "./modules/icons.js";
import { registerServiceWorker } from "./modules/service-worker.js";
import { enableFormDrafts, enableSmartInputs, enableQuickForms } from "./modules/forms.js";
import { enableIngredientBuilders } from "./modules/ingredients.js";
import { enableFamilyCenter } from "./modules/family-center.js";
import {
  enableReveal,
  enableParallax,
  enablePointerGlow,
  enableSwipeCards,
  fireConfetti,
} from "./modules/effects.js";
import { maybeStartOnboarding } from "./modules/onboarding.js";
import { initNotifications } from "./modules/push.js";
import { enableDateMask } from "./modules/date-mask.js";

window.Alpine = Alpine;
window.htmx = htmx;
window.Shepherd = Shepherd;
Alpine.start();

document.addEventListener("DOMContentLoaded", () => {
  createIcons({ icons, attrs: { "stroke-width": 1.8 } });
  registerServiceWorker();
  enableSwipeCards();
  enableReveal();
  enableParallax();
  enablePointerGlow();
  enableQuickForms();
  enableIngredientBuilders();
  enableFormDrafts();
  enableSmartInputs();
  enableDateMask();
  enableFamilyCenter();
  if (window.location.search.includes("celebrate=1")) {
    fireConfetti();
  }
  maybeStartOnboarding();
  initNotifications();
});

window.KinNet = { fireConfetti };
