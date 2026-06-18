// Minimal service worker: required for PWA installability + share target.
// Network-first navigation so shared URLs (?url=...) always reach the live app shell.
const CACHE = "macroreel-v4";
const APP_SHELL = ["/", "/index.html", "/manifest.webmanifest", "/macroreel-icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(APP_SHELL)).catch(() => undefined),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k.startsWith("macroreel-") && k !== CACHE).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method === "POST" && url.pathname === "/import-share") {
    event.respondWith(handleShareTarget(request));
    return;
  }
  if (request.method !== "GET") return;
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/index.html").then((r) => r || fetch(request))),
    );
    return;
  }
  event.respondWith(
    fetch(request).catch(() => caches.match(request)),
  );
});

async function handleShareTarget(request) {
  try {
    const formData = await request.formData();
    const title = (formData.get("title") || "").toString();
    const text = (formData.get("text") || "").toString();
    const url = (formData.get("url") || "").toString();
    const fileNames = formData
      .getAll("files")
      .filter((item) => typeof File !== "undefined" && item instanceof File && item.name)
      .map((file) => file.name)
      .join(" ");
    const shared = [url, text, title, fileNames].filter(Boolean).join(" ");
    const params = new URLSearchParams();
    if (shared) params.set("url", shared);
    else params.set("autorun", "0");
    return Response.redirect(`/import?${params.toString()}`, 303);
  } catch {
    return Response.redirect("/import?autorun=0", 303);
  }
}
