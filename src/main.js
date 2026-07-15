import "./style.css";

const sectionQuery = "main > section";
const sections = Array.from(document.querySelectorAll(sectionQuery));
const snapBreakpoint = window.matchMedia(
  "(min-width: 1024px) and (min-height: 760px)",
);
const previewBar = document.querySelector("#preview-bar");
const siteHeader = document.querySelector("#site-header");

let currentSectionIndex = 0;
let isSectionScrolling = false;
let targetSectionIndex = 0;
let scrollEndTimer = 0;
let lastWheelTime = 0;

if ("scrollRestoration" in history) {
  history.scrollRestoration = "manual";
}

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

function getStickyOffset() {
  const previewHeight = previewBar?.offsetHeight ?? 0;
  const headerHeight = siteHeader?.offsetHeight ?? 0;

  return previewHeight + headerHeight;
}

function getCurrentSectionIndex() {
  const stickyOffset = getStickyOffset();

  return sections.reduce((nearestIndex, section, index) => {
    const nearestDistance = Math.abs(
      sections[nearestIndex].getBoundingClientRect().top - stickyOffset,
    );
    const sectionDistance = Math.abs(
      section.getBoundingClientRect().top - stickyOffset,
    );

    return sectionDistance < nearestDistance ? index : nearestIndex;
  }, 0);
}

function getScrollStep(deltaY) {
  const scrollStrength = Math.abs(deltaY);

  if (scrollStrength >= 900) {
    return 3;
  }

  if (scrollStrength >= 450) {
    return 2;
  }

  return 1;
}

function scrollToSection(index) {
  const nextIndex = Math.max(0, Math.min(index, sections.length - 1));

  targetSectionIndex = nextIndex;
  isSectionScrolling = true;

  window.scrollTo({
    top: sections[targetSectionIndex].offsetTop - getStickyOffset(),
    behavior: "smooth",
  });

  window.clearTimeout(scrollEndTimer);

  scrollEndTimer = window.setTimeout(() => {
    isSectionScrolling = false;
    currentSectionIndex = getCurrentSectionIndex();
    targetSectionIndex = currentSectionIndex;
  }, 850);
}

function handleSectionWheel(event) {
  if (!snapBreakpoint.matches || sections.length === 0) {
    return;
  }

  event.preventDefault();

  const now = Date.now();

  if (Math.abs(event.deltaY) < 10 || now - lastWheelTime < 160) {
    return;
  }

  lastWheelTime = now;

  const direction = Math.sign(event.deltaY);
  const step = getScrollStep(event.deltaY);
  const baseIndex = isSectionScrolling
    ? targetSectionIndex
    : getCurrentSectionIndex();

  currentSectionIndex = baseIndex;
  scrollToSection(baseIndex + direction * step);
}

function handleSectionKeys(event) {
  if (!snapBreakpoint.matches || sections.length === 0) {
    return;
  }

  const nextKeys = ["ArrowDown", "PageDown", " "];
  const previousKeys = ["ArrowUp", "PageUp"];

  if (![...nextKeys, ...previousKeys].includes(event.key)) {
    return;
  }

  event.preventDefault();

  const baseIndex = isSectionScrolling
    ? targetSectionIndex
    : getCurrentSectionIndex();

  if (nextKeys.includes(event.key)) {
    scrollToSection(baseIndex + 1);
  } else {
    scrollToSection(baseIndex - 1);
  }
}

function resetToTop() {
  const originalScrollBehavior = document.documentElement.style.scrollBehavior;

  document.documentElement.style.scrollBehavior = "auto";
  window.scrollTo(0, 0);
  currentSectionIndex = 0;
  targetSectionIndex = 0;

  window.requestAnimationFrame(() => {
    document.documentElement.style.scrollBehavior = originalScrollBehavior;
  });
}

updateStickyOffsets();
resetToTop();

window.addEventListener("wheel", handleSectionWheel, { passive: false });
window.addEventListener("keydown", handleSectionKeys);
window.addEventListener("resize", updateStickyOffsets);
window.addEventListener("load", () => {
  updateStickyOffsets();
  resetToTop();
});
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    updateStickyOffsets();
    resetToTop();
  }
});
