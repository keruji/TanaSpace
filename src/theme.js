export function initTheme() {
  const root = document.documentElement;
  const toggles = [...document.querySelectorAll("[data-theme-toggle]")];
  const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");

  function savedTheme() {
    try {
      const theme = localStorage.getItem("tanaspace-theme")
        || localStorage.getItem("tanaspace-landing-theme");
      return theme === "light" || theme === "dark" ? theme : null;
    } catch (_) {
      return null;
    }
  }

  function applyTheme(theme) {
    root.dataset.theme = theme;
    for (const toggle of toggles) {
      toggle.setAttribute("aria-pressed", String(theme === "dark"));
      toggle.title = theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
    }
  }

  function syncTheme() {
    applyTheme(savedTheme() || (systemTheme.matches ? "dark" : "light"));
  }

  syncTheme();
  for (const toggle of toggles) {
    toggle.addEventListener("click", () => {
      const theme = root.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(theme);
      try {
        localStorage.setItem("tanaspace-theme", theme);
        localStorage.removeItem("tanaspace-landing-theme");
      } catch (_) {
        // The toggle still works for this visit when storage is unavailable.
      }
    });
  }
  systemTheme.addEventListener("change", () => {
    if (!savedTheme()) syncTheme();
  });
  window.addEventListener("storage", (event) => {
    if (event.key === null || ["tanaspace-theme", "tanaspace-landing-theme"].includes(event.key)) {
      syncTheme();
    }
  });
  window.addEventListener("pageshow", syncTheme);
}
