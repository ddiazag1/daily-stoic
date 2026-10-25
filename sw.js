/* Daily Stoic service worker: precache the whole book, serve it offline.
   VERSION is stamped by scripts/build.py from a hash of the app files and data,
   so any change produces a new cache and old caches are deleted. */
const VERSION = "39f0adde7c";
const CACHE = `daily-stoic-${VERSION}`;
const ASSETS = [
  "./",
  "index.html",
  "styles.css",
  "app.js",
  "data/entries.json",
  "manifest.webmanifest",
  "fonts/spectral-200.woff2",
  "fonts/spectral-400.woff2",
  "fonts/spectral-400-italic.woff2",
  "fonts/spectral-600.woff2",
  "icons/icon.svg",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-maskable-512.png",
  "icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  // Fetch each asset fresh (bypassing the HTTP cache) and store it under its plain path.
  event.waitUntil(
    caches.open(CACHE)
      .then((c) => Promise.all(ASSETS.map((u) =>
        fetch(new Request(`${u}?v=${VERSION}`, { cache: "reload" })).then((res) => {
          if (!res.ok) throw new Error(`${u} ${res.status}`);
          return c.put(u, res);
        }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("daily-stoic-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // Pages: network first (to pick up a new version), cached shell when offline.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("index.html", { ignoreSearch: true }))
    );
    return;
  }
  // Everything else: cache first, then network (and keep a copy).
  event.respondWith(
    caches.match(req, { ignoreSearch: true }).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok && res.type === "basic") {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy));
      }
      return res;
    }))
  );
});
