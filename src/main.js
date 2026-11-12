import "./style.css";
import { initScrollReveal } from "./scroll-reveal.js";

const previewBar = document.querySelector("#preview-bar");
const siteHeader = document.querySelector("#site-header");
const themeToggle = document.querySelector("#theme-toggle");

function updateThemeToggle() {
  if (themeToggle) {
    const darkMode = document.documentElement.dataset.theme === "dark";
    themeToggle.setAttribute(
      "aria-pressed",
      String(darkMode),
    );
    themeToggle.title = darkMode ? "Switch to light mode" : "Switch to dark mode";
  }
}

updateThemeToggle();
themeToggle?.addEventListener("click", () => {
  const useDarkTheme = document.documentElement.dataset.theme !== "dark";
  if (useDarkTheme) {
    document.documentElement.dataset.theme = "dark";
  } else {
    delete document.documentElement.dataset.theme;
  }
  updateThemeToggle();

  try {
    localStorage.setItem("tanaspace-landing-theme", useDarkTheme ? "dark" : "light");
  } catch (_) {
    // The toggle still works for this visit when browser storage is unavailable.
  }
});

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
