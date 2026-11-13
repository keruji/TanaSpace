import "./style.css";
import { initScrollReveal } from "./scroll-reveal.js";
import { initTheme } from "./theme.js";

const previewBar = document.querySelector("#preview-bar");
const siteHeader = document.querySelector("#site-header");
initTheme();

function updateStickyOffsets() {
  const previewHeight = previewBar?.offsetHeight ?? 0;
  const headerHeight = siteHeader?.offsetHeight ?? 0;
  const stickyOffset = previewHeight + headerHeight;

  document.documentElement.style.setProperty(
    "--preview-height",
    `${previewHeight}px`,
  );
  document.documentElement.style.setProperty(
    "--sticky-offset",
    `${stickyOffset}px`,
  );
}

updateStickyOffsets();

window.addEventListener("resize", updateStickyOffsets);
window.addEventListener("load", updateStickyOffsets);
window.addEventListener("pageshow", updateStickyOffsets);

// Measure lines after the page's fonts have settled.
document.fonts.ready.then(initScrollReveal);
