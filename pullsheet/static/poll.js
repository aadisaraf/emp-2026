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
        set("[data-poll='word']", s.word);
        set("[data-poll='detail']", s.detail);
        set("[data-poll='pull']", String(s.pull_count));
        set("[data-poll='held']", String(s.held_count));
        set("[data-poll='new']", String(s.new_count));
        (s.deadlines || []).forEach(function (d) {
          set("[data-deadline='" + d.key + "'] .clock", d.text);
        });

        /* A new run changes the shape of the page, not just its numbers --
           different lines, a different date, a different corpus. Reload once
           rather than trying to rebuild the tables here. */
        var seen = document.body.getAttribute("data-run");
        var current = String(s.run_id === null ? "" : s.run_id);
        if (seen !== null && seen !== current) { window.location.reload(); }
        document.body.setAttribute("data-run", current);
      })
      .catch(function () { /* a failed poll changes nothing on the page */ });
  }

  tick();
  window.setInterval(tick, EVERY_MS);
})();
