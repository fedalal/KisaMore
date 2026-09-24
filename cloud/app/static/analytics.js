// One event per document load. API polling and modal changes do not call this.
(() => {
  if (location.pathname !== '/' || navigator.webdriver) return;
  const params = new URLSearchParams(location.search);
  const payload = {
    event_id: crypto.randomUUID(), path: location.pathname,
    source: (params.get('utm_source') || '').slice(0, 100),
    medium: (params.get('utm_medium') || '').slice(0, 100),
    campaign: (params.get('utm_campaign') || '').slice(0, 100),
    referrer: document.referrer.slice(0, 2048)
  };
  const send = () => fetch('/api/v1/analytics/visit', {
    method: 'POST', credentials: 'same-origin', keepalive: true,
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
  }).then(r => { if (!r.ok) throw new Error('Tracking unavailable'); });
  // Reuse the event ID so a retry cannot count the same view twice.
  send().catch(() => new Promise(resolve => setTimeout(resolve, 2000)).then(send)).catch(() => {});
})();
