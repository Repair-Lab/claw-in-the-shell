// GhostShell OS — Service Worker v0.13.0
// Caching-Strategie: Network-First mit Offline-Fallback

const CACHE_NAME = 'ghostshell-v0.13.0';
const OFFLINE_URL = '/offline.html';

// Dateien die beim Install vorgeladen werden
const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/logo.svg',
  '/offline.html',
];

// Install: Precache Dateien
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[SW] Precaching:', PRECACHE_URLS.length, 'Dateien');
      return cache.addAll(PRECACHE_URLS);
    })
  );
  self.skipWaiting();
});

// Activate: Alte Caches löschen
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => {
            console.log('[SW] Lösche alten Cache:', key);
            return caches.delete(key);
          })
      )
    )
  );
  self.clients.claim();
});

// Fetch: Network-First für API, Cache-First für Assets
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // API-Calls: Immer Netzwerk, kein Cache
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(event.request).catch(() =>
        new Response(JSON.stringify({ error: 'Offline — keine Verbindung zum Ghost-Kernel' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    );
    return;
  }

  // WebSocket: Durchlassen
  if (event.request.url.startsWith('ws://') || event.request.url.startsWith('wss://')) {
    return;
  }

  // Alles andere: Network-First mit Cache-Fallback
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Gültige Response cachen
        if (response.ok && event.request.method === 'GET') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(async () => {
        const cached = await caches.match(event.request);
        if (cached) return cached;

        // Navigation → Offline-Seite
        if (event.request.mode === 'navigate') {
          const offlinePage = await caches.match(OFFLINE_URL);
          if (offlinePage) return offlinePage;
        }

        return new Response('Offline', { status: 503 });
      })
  );
});

// Background Sync: Sensor-Daten nachladen wenn online
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-sensor-data') {
    event.waitUntil(syncSensorData());
  }
});

async function syncSensorData() {
  try {
    // Pending Sensor-Daten aus IndexedDB holen und an API senden
    console.log('[SW] Background Sync: Sensor-Daten werden übertragen...');
    // Implementation wird vom Frontend befüllt
  } catch (err) {
    console.error('[SW] Sync fehlgeschlagen:', err);
  }
}

// Push Notifications (vorbereitet)
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(data.title || 'GhostShell', {
      body: data.body || 'Neue Nachricht vom Ghost-Kernel',
      icon: '/logo.svg',
      badge: '/icons/ghost-192.png',
      tag: data.tag || 'ghost-notification',
      data: data.url ? { url: data.url } : undefined,
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(clients.openWindow(url));
});
