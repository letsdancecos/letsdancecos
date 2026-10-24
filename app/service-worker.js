const CACHE_NAME = "letsdance-studio-app-v6";
const APP_FILES = ["./", "./index.html", "./manifest-dancer.webmanifest", "./icon-dancer-v3-32.png", "./icon-dancer-v3-180.png", "./icon-dancer-v3-192.png", "./icon-dancer-v3-512.png", "./icon-dancer-v3-maskable-512.png"];
self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith("letsdance-studio-app-") && k !== CACHE_NAME).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", event => {
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== self.location.origin) return;
  if (new URL(event.request.url).pathname.endsWith("/announcements.json")) {
    event.respondWith(fetch(event.request, {cache: "no-store"}));
    return;
  }
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("./index.html")));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});
