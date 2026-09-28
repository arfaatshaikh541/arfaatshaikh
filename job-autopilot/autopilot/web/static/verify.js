// Remote verification client. Loaded only on /verify/<id>; CSP allows only this file and a same-host WebSocket.
(function () {
  "use strict";
  var root = document.getElementById("rv");
  if (!root) return;
  var vid = root.getAttribute("data-vid");
  var img = document.getElementById("rv-img");
  var status = document.getElementById("rv-status");
  var viewport = [1366, 900];
  var lastUrl = null;
  var proto = location.protocol === "https:" ? "wss://" : "ws://";
  var ws = new WebSocket(proto + location.host + "/verify/" + vid + "/ws");
  ws.binaryType = "blob";
  function say(t, cls) { status.textContent = t; status.className = cls || "muted"; }
  function send(o) { if (ws.readyState === 1) ws.send(JSON.stringify(o)); }
  ws.onopen = function () { say("Connected. Waiting for the first frame…", "info"); };
  ws.onmessage = function (ev) {
    if (typeof ev.data === "string") {
      var m; try { m = JSON.parse(ev.data); } catch (e) { return; }
      if (m.type === "hello" && m.viewport) viewport = m.viewport;
      if (m.type === "status") say(m.message || m.state, m.state === "closed" ? "ok" : (m.state === "error" ? "bad" : "warn"));
      return;
    }
    var url = URL.createObjectURL(ev.data);
    img.onload = function () { if (lastUrl) URL.revokeObjectURL(lastUrl); lastUrl = url; };
    img.src = url;
  };
  ws.onclose = function () { say("Session ended. Reload this page to see the result.", "muted"); };
  img.addEventListener("click", function (e) {
    var r = img.getBoundingClientRect();
    send({ type: "click", x: (e.clientX - r.left) * viewport[0] / r.width, y: (e.clientY - r.top) * viewport[1] / r.height });
  });
  img.addEventListener("wheel", function (e) { e.preventDefault(); send({ type: "scroll", dy: e.deltaY }); }, { passive: false });
  document.getElementById("rv-up").addEventListener("click", function () { send({ type: "scroll", dy: -500 }); });
  document.getElementById("rv-down").addEventListener("click", function () { send({ type: "scroll", dy: 500 }); });
  var box = document.getElementById("rv-text");
  document.getElementById("rv-send").addEventListener("click", function () {
    if (box.value) { send({ type: "type", text: box.value }); box.value = ""; }
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-key]"), function (b) {
    b.addEventListener("click", function () { send({ type: "key", key: b.getAttribute("data-key") }); });
  });
  document.getElementById("rv-done").addEventListener("click", function () {
    send({ type: "done" }); say("Checking whether the challenge is cleared…", "warn");
  });
})();
