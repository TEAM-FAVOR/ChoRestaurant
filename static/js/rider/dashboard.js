(function () {
  const table = document.querySelector("[data-rider-dashboard]");
  if (!table) return;

  const sockets = {};

  function getCookie(name) {
    const parts = document.cookie ? document.cookie.split("; ") : [];
    for (const part of parts) {
      if (part.startsWith(name + "=")) return decodeURIComponent(part.slice(name.length + 1));
    }
    return "";
  }

  function statusLabel(status) {
    return status.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function updateRow(row, data) {
    if (!data || !data.status) return;
    row.dataset.deliveryStatus = data.status;
    const badge = row.querySelector(".status");
    if (badge) {
      badge.textContent = statusLabel(data.status);
      badge.className = "status status-" + data.status.toLowerCase();
    }
    const eta = row.querySelector("[data-eta]");
    if (eta) eta.textContent = data.eta_minutes ? data.eta_minutes + " min" : "—";
  }

  function connectRow(row) {
    const deliveryId = row.dataset.deliveryId;
    if (!deliveryId || sockets[deliveryId]) return;
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const endpoint = scheme + "//" + window.location.host + "/ws/delivery/" + deliveryId + "/";
    try {
      const socket = new WebSocket(endpoint);
      sockets[deliveryId] = socket;
      socket.onmessage = function (event) {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "status" || data.type === "eta") updateRow(row, data);
        } catch (error) {
          console.error(error);
        }
      };
      socket.onclose = function () {
        delete sockets[deliveryId];
        window.setTimeout(function () { connectRow(row); }, 5000);
      };
    } catch (error) {
      console.error(error);
    }
  }

  table.querySelectorAll("tr[data-delivery-id]").forEach(connectRow);

  window.setInterval(function () {
    fetch(table.dataset.refreshUrl, {
      headers: {
        Accept: "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      }
    })
      .then(function (response) { return response.ok ? response.json() : []; })
      .then(function (items) {
        items.forEach(function (item) {
          const row = table.querySelector('tr[data-delivery-id="' + item.id + '"]');
          if (row) updateRow(row, item);
        });
      })
      .catch(function (error) { console.error(error); });
  }, 15000);
})();
