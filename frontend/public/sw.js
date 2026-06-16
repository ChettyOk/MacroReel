// Minimal service worker: required for PWA installability + share target.
// Network-first navigation so shared URLs (?url=...) always reach the live app shell.
const CACHE = "macroreel-v3";
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
