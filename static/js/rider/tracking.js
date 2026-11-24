(function () {
  const panel = document.querySelector("[data-tracking-map]");
  if (!panel || typeof window.L === "undefined") return;

  const deliveryId = panel.dataset.deliveryId;
  const mode = panel.dataset.mode;
  const statusUrl = panel.dataset.statusUrl;
  const locationUrl = panel.dataset.locationUrl;
  const detailUrl = panel.dataset.detailUrl;
  const trackUrl = panel.dataset.trackUrl;
  const fallbackUrl = mode === "rider" ? detailUrl : trackUrl;
  const restaurant = { lat: 5.603717, lng: -0.186964 };
  const map = L.map("delivery-map").setView([restaurant.lat, restaurant.lng], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);

  const restaurantMarker = L.marker([restaurant.lat, restaurant.lng]).addTo(map);
  restaurantMarker.bindPopup("Cho Restaurant");

  let riderMarker = null;
  let destinationMarker = null;
  let routeLine = null;
  let socket = null;
  let currentStatus = panel.dataset.deliveryStatus || "";
  let watchId = null;

  function number(value) {
    if (value === "" || value === null || typeof value === "undefined") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function cookie(name) {
    const parts = document.cookie ? document.cookie.split("; ") : [];
    for (const part of parts) {
      if (part.startsWith(name + "=")) return decodeURIComponent(part.slice(name.length + 1));
    }
    return "";
  }

  async function postJSON(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cookie("csrftoken")
      },
      body: JSON.stringify(body || {})
    });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || data.message || "Request failed");
    }
    return response.json();
  }

  async function getJSON(url) {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) return null;
    return response.json();
  }

  function updateStatus(status) {
    currentStatus = status;
    const badge = panel.querySelector("[data-status-badge]");
    if (badge) {
      badge.textContent = status.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
      badge.className = "status status-" + status.toLowerCase();
    }
  }

  function updateEta(value) {
    const node = panel.querySelector("[data-eta]");
    if (!node) return;
    node.textContent = value ? value + " min" : "—";
  }

  function updateRider(lat, lng) {
    const latitude = number(lat);
    const longitude = number(lng);
    if (latitude === null || longitude === null) return;
    const position = [latitude, longitude];
    if (riderMarker) {
      riderMarker.setLatLng(position);
    } else {
      riderMarker = L.marker(position).addTo(map);
      riderMarker.bindPopup("Rider");
    }
    drawRoute();
  }

  function updateDestination(lat, lng) {
    const latitude = number(lat);
    const longitude = number(lng);
    if (latitude === null || longitude === null) return;
    if (!destinationMarker) {
      destinationMarker = L.marker([latitude, longitude]).addTo(map);
      destinationMarker.bindPopup("Delivery destination");
    } else {
      destinationMarker.setLatLng([latitude, longitude]);
    }
    drawRoute();
  }

  function drawRoute() {
    const destinationLat = number(panel.dataset.destinationLat);
    const destinationLng = number(panel.dataset.destinationLng);
    const riderLat = riderMarker ? riderMarker.getLatLng().lat : number(panel.dataset.riderLat);
    const riderLng = riderMarker ? riderMarker.getLatLng().lng : number(panel.dataset.riderLng);
    if (!destinationMarker || riderLat === null || riderLng === null) return;
    const points = [[riderLat, riderLng], [destinationMarker.getLatLng().lat, destinationMarker.getLatLng().lng]];
    if (routeLine) {
      routeLine.setLatLngs(points);
    } else {
      routeLine = L.polyline(points, { color: "#17643f", dashArray: "6 6" }).addTo(map);
    }
    map.fitBounds(L.latLngBounds(points), { padding: [40, 40] });
  }

  function applySnapshot(data) {
    if (!data) return;
    if (data.status) updateStatus(data.status);
    if (data.eta_minutes !== undefined) updateEta(data.eta_minutes);
    if (data.current_lat || data.current_lng) updateRider(data.current_lat, data.current_lng);
    if (data.destination_lat || data.destination_lng) {
      updateDestination(data.destination_lat, data.destination_lng);
    }
    if (data.rider && data.rider.current_lat) updateRider(data.rider.current_lat, data.rider.current_lng);
  }

  function handleMessage(data) {
    if (!data) return;
    if (data.type === "status") updateStatus(data.status);
    if (data.type === "eta") updateEta(data.eta_minutes);
    if (data.type === "location") {
      updateRider(data.lat, data.lng);
      if (data.eta_minutes !== undefined) updateEta(data.eta_minutes);
    }
  }

  function connect() {
    if (!deliveryId || !window.WebSocket) return;
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const endpoint = scheme + "//" + window.location.host + "/ws/delivery/" + deliveryId + "/";
    try {
      socket = new WebSocket(endpoint);
      socket.onmessage = function (event) {
        try { handleMessage(JSON.parse(event.data)); } catch (error) { console.error(error); }
      };
      socket.onclose = function () {
        socket = null;
        window.setTimeout(connect, 5000);
      };
    } catch (error) {
      console.error(error);
    }
  }

  function poll() {
    if (!fallbackUrl) return;
    getJSON(fallbackUrl).then(applySnapshot);
  }

  function showGpsError(message) {
    const node = panel.querySelector("[data-gps-error]");
    if (!node) return;
    node.textContent = message;
    node.hidden = false;
  }

  async function shareLocation(position) {
    if (currentStatus !== "IN_TRANSIT") return;
    try {
      const data = await postJSON(locationUrl, {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude
      });
      updateRider(position.coords.latitude, position.coords.longitude);
      if (data && data.eta_minutes) updateEta(data.eta_minutes);
      const errorNode = panel.querySelector("[data-gps-error]");
      if (errorNode) errorNode.hidden = true;
    } catch (error) {
      showGpsError(error.message);
    }
  }

  function startGps() {
    if (mode !== "rider" || !locationUrl || !navigator.geolocation || watchId !== null) return;
    watchId = navigator.geolocation.watchPosition(
      shareLocation,
      (error) => showGpsError("Location unavailable: " + error.message),
      { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    );
  }

  async function updateStatusFromButton(event) {
    const button = event.currentTarget;
    const nextStatus = button.dataset.updateStatus;
    button.disabled = true;
    try {
      const data = await postJSON(statusUrl, { status: nextStatus });
      applySnapshot(data);
      if (nextStatus === "IN_TRANSIT") startGps();
      if (["DELIVERED", "FAILED", "CANCELLED"].includes(nextStatus) && watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
      }
    } catch (error) {
      showGpsError(error.message);
      button.disabled = false;
    }
  }

  updateDestination(panel.dataset.destinationLat, panel.dataset.destinationLng);
  updateRider(panel.dataset.riderLat, panel.dataset.riderLng);
  if (mode === "rider" && currentStatus === "IN_TRANSIT") startGps();
  panel.querySelectorAll("[data-update-status]").forEach((button) => {
    button.addEventListener("click", updateStatusFromButton);
  });
  poll();
  window.setInterval(poll, 15000);
  connect();
})();
