// Offline app shell only (spec 008, PWA-2). Product pages and API data are never cached here:
// a score must always come from the API so it matches the current engine_version.
const CACHE = "foodtrace-shell-v1";
const SHELL = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/p/")) return; // product data: network only

  const isShellAsset =
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/zxing/") ||
    SHELL.includes(url.pathname);

  if (request.mode === "navigate") {
    // Network first for pages; fall back to the cached home page when offline.
    event.respondWith(fetch(request).catch(() => caches.match("/")));
  } else if (isShellAsset) {
    event.respondWith(
      caches.match(request).then(
        (hit) =>
          hit ||
          fetch(request).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
            return res;
          }),
      ),
    );
  }
});
