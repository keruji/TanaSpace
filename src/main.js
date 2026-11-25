import "./style.css";
import { initTheme } from "./theme.js";
import { initWorkspace } from "./workspace.js";

initTheme();
initWorkspace();

const siteHeader = document.querySelector(".site-header");
if (siteHeader) {
  const updateHeaderHeight = () => {
    document.documentElement.style.setProperty(
      "--landing-header-height",
      `${siteHeader.getBoundingClientRect().height}px`,
    );
  };
  updateHeaderHeight();
  window.addEventListener("resize", updateHeaderHeight);
  window.addEventListener("pageshow", updateHeaderHeight);
}
