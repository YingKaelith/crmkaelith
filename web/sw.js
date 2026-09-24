'use strict';
/* Only generic offline content and public icons can enter this cache.
   Never cache API responses, documents containing business data, login requests,
   password/activation tokens, exports, or mutation responses. */
const CACHE = 'nexo-public-v3.0.0';
const PUBLIC_FILES = ['/offline.html', '/icons/icon-192.png', '/icons/icon-512.png', '/icons/maskable-512.png', '/icons/apple-touch-icon.png', '/icons/favicon-32.png'];
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(PUBLIC_FILES)));
  // A waiting update is never activated without closing clients or explicit consent.
});
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith('nexo-public-') && key !== CACHE) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener('message', event => {
  if (event.data?.type === 'ACTIVATE_UPDATE') self.skipWaiting();
});
self.addEventListener('fetch', event => {
  const request = event.request, url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(async () => {
      const cached = await (await caches.open(CACHE)).match('/offline.html');
      return cached || new Response('Sem conexão. Reconecte-se para acessar o Nexo CRM.', {status: 503, headers: {'Content-Type': 'text/plain; charset=utf-8'}});
    }));
    return;
  }
  if (!url.search && PUBLIC_FILES.includes(url.pathname)) {
    event.respondWith(caches.open(CACHE).then(async cache => (await cache.match(url.pathname)) || fetch(request)));
  }
});
