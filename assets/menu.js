// Close the profile menu when an item is chosen or when clicking anywhere outside it.
document.addEventListener("click", function (e) {
  document.querySelectorAll("details.profile-dd[open]").forEach(function (d) {
    if (!d.contains(e.target) || e.target.closest(".menu-item")) d.removeAttribute("open");
  });
});
// Esc closes whichever pop-up is open.
document.addEventListener("keydown", function (e) {
  if (e.key !== "Escape") return;
  var m = document.querySelector(".modal.open .modal-close");
  if (m) m.click();
});
// Close an open risk explanation when clicking elsewhere.
document.addEventListener("click", function (e) {
  document.querySelectorAll("details.risk-dd[open]").forEach(function (d) {
    if (!d.contains(e.target)) d.removeAttribute("open");
  });
});
// Only one explanation open at a time.
document.addEventListener("toggle", function (e) {
  var d = e.target;
  if (d.matches && d.matches("details.risk-dd") && d.open) {
    document.querySelectorAll("details.risk-dd[open]").forEach(function (o) { if (o !== d) o.removeAttribute("open"); });
  }
}, true);
// Review mode: click a highlighted phrase to pin its suggestion card open next to it.
// The card stays until you Accept, Reject, press its ×, or click anywhere else.
document.addEventListener("click", function (e) {
  var t = e.target;
  var openWraps = document.querySelectorAll("#ws-review .hl-wrap.open");
  if (t.closest && t.closest(".hl-close")) {
    openWraps.forEach(function (w) { w.classList.remove("open"); });
    return;
  }
  var mark = t.closest && t.closest("#ws-review .hl");
  if (mark) {
    var wrap = mark.parentElement;
    var wasOpen = wrap.classList.contains("open");
    openWraps.forEach(function (w) { w.classList.remove("open"); });
    if (!wasOpen) wrap.classList.add("open");
    return;
  }
  if (t.closest && t.closest("#ws-review .hl-card")) return;  // clicks inside the card (Accept/Reject) keep it
  openWraps.forEach(function (w) { w.classList.remove("open"); });
});
document.addEventListener("keydown", function (e) {
  if (e.key === "Escape") document.querySelectorAll("#ws-review .hl-wrap.open").forEach(function (w) { w.classList.remove("open"); });
});
// Pipeline: a click anywhere in a row opens that grant, except on the row's own controls
// (next-action button, Responsible dropdown, delete). Cells without their own target pass the click on.
document.addEventListener("click", function (e) {
  var row = e.target.closest && e.target.closest("tr.pipe-row");
  if (!row || e.target.closest(".cell-hit, button, a, input, .dash-dropdown, .Select, .dropdown, [role='option']")) return;
  var hit = row.querySelector(".cell-hit");
  if (hit) hit.click();
});
// Compass Assistant: open/close, Enter to send (Shift+Enter = new line), keep the newest message in view.
document.addEventListener("click", function (e) {
  var panel = document.getElementById("chat-panel");
  if (!panel) return;
  if (e.target.closest("#chat-launcher")) {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) setTimeout(function () { document.getElementById("chat-input").focus(); }, 50);
  } else if (e.target.closest("#chat-close")) {
    panel.classList.remove("open");
  } else if (panel.classList.contains("open") && e.target.isConnected && !e.target.closest(".chat-root")) {
    panel.classList.remove("open");  // a click anywhere outside the chat minimises it
  }
});
document.addEventListener("keydown", function (e) {
  if (e.target.id === "chat-input" && e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    var send = document.getElementById("chat-send");
    if (send && !send.disabled) send.click();
  } else if (e.key === "Escape") {
    var p = document.querySelector("#chat-panel.open");
    if (p && p.contains(document.activeElement)) p.classList.remove("open");
  }
});
new MutationObserver(function () {
  var log = document.getElementById("chat-log");
  if (log && log.dataset.h !== String(log.scrollHeight)) {  // a message arrived or the reply replaced the dots
    log.dataset.h = log.scrollHeight;
    log.scrollTop = log.scrollHeight;
  }
}).observe(document.documentElement, { childList: true, subtree: true });
// Application editor: open / close the Edit question form.
document.addEventListener("click", function (e) {
  if (e.target.closest("#ws-qedit-toggle")) {
    var f = document.getElementById("ws-qedit");
    if (f) f.classList.toggle("open");
  } else if (e.target.closest("#ws-qedit-cancel")) {
    var g = document.getElementById("ws-qedit");
    if (g) g.classList.remove("open");
  }
});
// After the server restarts (new code), reload this tab so it uses the new callbacks. Waits until you're not
// typing; the editor autosaves, so nothing is lost.
(function () {
  var loaded = null;
  setInterval(function () {
    var el = document.getElementById("build-id");
    if (!el) return;
    loaded = loaded || el.dataset.build;
    fetch("/__build", { cache: "no-store" }).then(function (r) { return r.ok ? r.text() : null; }).then(function (id) {
      var a = document.activeElement;
      var typing = a && (a.tagName === "TEXTAREA" || a.tagName === "INPUT");
      if (id && loaded && id !== loaded && !typing) location.reload();
    }).catch(function () {});  // server down for a moment: try again next time
  }, 5000);
})();
// Answer Library cards: expand / collapse the full answer.
document.addEventListener("click", function (e) {
  var b = e.target.closest(".ans-more");
  if (!b) return;
  var c = b.closest(".ans-card");
  c.classList.toggle("expanded");
  b.textContent = c.classList.contains("expanded") ? "Show less" : "Show full answer";
});
// Copy buttons: a click on the word "Copy" copies too (dcc.Clipboard only listens on its icon).
document.addEventListener("click", function (e) {
  var b = e.target.closest(".ans-copy");
  if (!b || e.target.closest(".ans-copy-icon")) return;
  var icon = b.querySelector(".ans-copy-icon");
  if (icon) (icon.querySelector("svg, i, span") || icon).dispatchEvent(new MouseEvent("click", { bubbles: true }));
});
// Numbers that count up when they appear (fit dials, fit badges).
(function () {
  function run(el) {
    var to = parseFloat(el.dataset.to); if (isNaN(to)) return;
    el.dataset.done = "1";
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = to; return; }
    var start = performance.now(), dur = 900;
    (function step(t) {
      var k = Math.min(1, (t - start) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = Math.round(to * e);
      if (k < 1) requestAnimationFrame(step);
    })(start);
  }
  new MutationObserver(function () {
    document.querySelectorAll(".count-up[data-to]:not([data-done])").forEach(run);
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
// Comments: pass the words selected in the answer to the app (enables "💬 Comment"),
// and clicking a comment's quote selects those words in the answer.
(function () {
  var last = null;
  function share() {
    var ta = document.getElementById("ws-text"), box = document.getElementById("cm-sel");
    if (!ta || !box) return;
    var sel = ta.value.slice(ta.selectionStart, ta.selectionEnd).trim().slice(0, 500);
    if (sel === last) return;
    last = sel;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(box, sel);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  }
  ["mouseup", "keyup", "select"].forEach(function (ev) {
    document.addEventListener(ev, function (e) { if (e.target.id === "ws-text") setTimeout(share, 0); });
  });
  document.addEventListener("click", function (e) {
    var q = e.target.closest(".cm-quote[data-quote]");
    if (!q) return;
    var edit = document.querySelector("#ws-mode input[value='edit']");
    if (edit && !edit.checked) edit.click();  // the words are selectable in Edit mode
    setTimeout(function () {
      var ta = document.getElementById("ws-text"), quote = q.dataset.quote, i = ta ? ta.value.indexOf(quote) : -1;
      if (i < 0) return;
      ta.focus();
      ta.setSelectionRange(i, i + quote.length);
      var before = ta.value.slice(0, i).split("\n").length;  // scroll the selection into view
      ta.scrollTop = Math.max(0, (before - 3) * parseFloat(getComputedStyle(ta).lineHeight || 22));
    }, 150);
  });
})();
