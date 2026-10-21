// Same-origin app cache only. Never intercept translation providers or arXiv.
const CACHE='hep-match-shell-v1';
const ASSETS=['./','./index.html','./styles.css','./app.mjs','./core.mjs','./math-config.js','./icon.svg','./manifest.webmanifest'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('hep-match-shell-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET'||new URL(event.request.url).origin!==self.location.origin)return;
  event.respondWith((async()=>{
    const cache=await caches.open(CACHE);
    try{
      const response=await fetch(event.request,{signal:AbortSignal.timeout(10000)});
      if(response.ok)await cache.put(event.request,response.clone());
      return response;
    }catch{
      const cached=await cache.match(event.request);
      if(cached)return cached;
      return new Response('Offline; open once online to cache the app.',{status:503,headers:{'Content-Type':'text/plain;charset=utf-8'}});
    }
  })());
});
