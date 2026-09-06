/* The only JavaScript in PullSheet.
 *
 * It updates numbers that are already on the page. It does not decide anything,
 * it does not hide anything, and if it never runs the page is still complete and
 * still correct -- just not self-refreshing. That is the whole contract, and it
 * is why the demo does not depend on this file working.
 */
(function () {
  "use strict";
  var EVERY_MS = 2000;

  function set(sel, text) {
    document.querySelectorAll(sel).forEach(function (el) {
      if (el.textContent !== text) { el.textContent = text; }
    });
  }

  function tick() {
    fetch("/api/status", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (s) {
        if (!s) { return; }
        set("[data-poll='pull']", String(s.pull_count));
        set("[data-poll='held']", String(s.held_count));
        set("[data-poll='sites']", String(s.sites.length));

        (s.site_status || []).forEach(function (row) {
          var sel = "[data-site-status='" + CSS.escape(row.site) + "']";
          set(sel + " .status-word", row.status);
          set(sel + " .site-reason", row.reason);
        });
        (s.deadlines || []).forEach(function (d) {
          set("[data-deadline='" + d.key + "'] .clock", d.text);
        });

        /* A newly ingested export changes the shape of the page, not just its
           numbers. Reload once rather than trying to rebuild the table here. */
        var seen = document.body.getAttribute("data-ingest");
        var current = String(s.last_ingest ? s.last_ingest.id : "");
        if (seen !== null && seen !== current) { window.location.reload(); }
        document.body.setAttribute("data-ingest", current);
      })
      .catch(function () { /* a failed poll changes nothing on the page */ });
  }

  tick();
  window.setInterval(tick, EVERY_MS);
})();
