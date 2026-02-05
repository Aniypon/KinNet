// Web push subscription + in-app notification bell.

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; ++i) output[i] = raw.charCodeAt(i);
  return output;
}

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : "";
}

async function postJSON(url, body) {
  return fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRFToken": getCsrf() },
    body: body ? JSON.stringify(body) : undefined,
  });
}

async function getVapidKey() {
  const res = await fetch("/api/push/vapid", { credentials: "same-origin" });
  if (!res.ok) return "";
  const { public_key } = await res.json();
  return public_key || "";
}

export async function ensurePushSubscription() {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return;
  if (!("Notification" in window)) return;
  if (Notification.permission === "denied") return;

  const publicKey = await getVapidKey();
  if (!publicKey) return;

  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    if (Notification.permission === "default") {
      const perm = await Notification.requestPermission();
      if (perm !== "granted") return;
    }
    try {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      });
    } catch (e) {
      console.warn("[KinNet] push subscribe failed", e);
      return;
    }
  }
  const json = sub.toJSON();
  await postJSON("/api/push/subscribe", {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    user_agent: navigator.userAgent.slice(0, 240),
  });
}

export async function renderUnreadBadge() {
  const host = document.querySelector("[data-notifications-feed]");
  if (!host) return;
  const res = await fetch("/api/notifications?limit=10", { credentials: "same-origin" });
  if (!res.ok) return;
  const items = await res.json();
  const badge = document.querySelector("[data-notifications-count]");
  const unread = items.filter((n) => !n.is_read).length;
  if (badge) {
    badge.textContent = unread || "";
    badge.hidden = !unread;
  }
  const clearBtnEl = document.querySelector("[data-notifications-clear]");
  if (clearBtnEl) clearBtnEl.hidden = !unread;
  host.innerHTML = "";
  if (!items.length) {
    host.innerHTML = '<p class="meta">Пока тишина.</p>';
  } else {
    for (const n of items) {
      const a = document.createElement("a");
      a.href = n.url || "#";
      a.className = "notif-item" + (n.is_read ? " notif-item--read" : "");
      a.dataset.notifId = n.id;
      a.innerHTML = `<strong>${escapeHtml(n.title)}</strong>` +
        (n.body ? `<span class="meta">${escapeHtml(n.body)}</span>` : "");
      a.addEventListener("click", () => {
        postJSON(`/api/notifications/${n.id}/read`).catch(() => {});
      });
      host.appendChild(a);
    }
  }
  const clearBtn = document.querySelector("[data-notifications-clear]");
  if (clearBtn && !clearBtn.dataset.bound) {
    clearBtn.dataset.bound = "1";
    clearBtn.addEventListener("click", async () => {
      await postJSON("/api/notifications/read-all");
      renderUnreadBadge();
    });
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

export function initNotifications() {
  ensurePushSubscription().catch(() => {});
  renderUnreadBadge().catch(() => {});
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.addEventListener("message", (ev) => {
      if (ev.data && ev.data.type === "notification") renderUnreadBadge();
    });
  }
  connectSSE();
  setInterval(() => renderUnreadBadge().catch(() => {}), 60_000);
}

function showToast(payload) {
  let host = document.querySelector("[data-toast-host]");
  if (!host) {
    host = document.createElement("div");
    host.dataset.toastHost = "1";
    host.className = "toast-host";
    document.body.appendChild(host);
  }
  const t = document.createElement("a");
  t.className = "toast";
  t.href = payload.url || "#";
  t.innerHTML = `<strong>${escapeHtml(payload.title || "")}</strong>` +
    (payload.body ? `<span class="meta">${escapeHtml(payload.body)}</span>` : "");
  host.appendChild(t);
  setTimeout(() => t.classList.add("toast--out"), 4500);
  setTimeout(() => t.remove(), 5000);
}

function connectSSE() {
  if (!("EventSource" in window)) return null;
  if (!document.body.dataset.userAuthenticated) return null;
  const es = new EventSource("/notifications/stream/");
  es.addEventListener("notification", (ev) => {
    try {
      showToast(JSON.parse(ev.data));
    } catch (_) {}
    renderUnreadBadge().catch(() => {});
  });
  return es;
}
