/* remote-comfy project page: theme switch and the copy button. No inline script, for the site's CSP. */
(function () {
  "use strict";
  var root = document.documentElement;

  /* theme: follows the system until the visitor chooses */
  var themeBtn = document.getElementById("theme");
  function currentTheme() {
    return root.getAttribute("data-theme") || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  }
  function paintTheme() { themeBtn.textContent = "Theme: " + currentTheme(); }
  try {
    var saved = window.localStorage.getItem("rc-theme");
    if (saved === "light" || saved === "dark" || saved === "1997") root.setAttribute("data-theme", saved);
  } catch (e) {}
  var forced = /[?&]theme=(light|dark|1997)/.exec(window.location.search);
  if (forced) root.setAttribute("data-theme", forced[1]);
  themeBtn.addEventListener("click", function () {
    var order = ["dark", "light", "1997"];
    var next = order[(order.indexOf(currentTheme()) + 1) % order.length];
    root.setAttribute("data-theme", next);
    try { window.localStorage.setItem("rc-theme", next); } catch (e) {}
    paintTheme();
  });
  paintTheme();

  /* the line to paste */
  var copyLine = document.getElementById("copy-line");
  if (copyLine && navigator.clipboard) {
    copyLine.hidden = false;
    copyLine.addEventListener("click", function () {
      navigator.clipboard.writeText(document.getElementById("the-line").textContent).then(function () {
        copyLine.textContent = "Copied";
        setTimeout(function () { copyLine.textContent = "Copy"; }, 1600);
      });
    });
  }
})();
