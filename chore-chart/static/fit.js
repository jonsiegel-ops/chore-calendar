// Size the page to the area the browser actually shows. On touch screens like the
// fridge, a 100% height includes the space behind the browser's toolbars, which
// pushes the bottom of the page off screen.
(function () {
  "use strict";
  function fit() {
    document.documentElement.style.setProperty("--app-height", window.innerHeight + "px");
  }
  fit();
  window.addEventListener("resize", fit);
  window.addEventListener("orientationchange", fit);
  if (window.visualViewport) window.visualViewport.addEventListener("resize", fit);
})();
