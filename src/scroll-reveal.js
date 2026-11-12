// Reveal text lines and whole elements without changing document scrolling.
export function initScrollReveal() {
  const elements = [...document.querySelectorAll("[data-scroll-reveal]")]
    .filter((element) => !element.parentElement.closest('[data-scroll-reveal="element"]'));
  const textElements = elements.filter((element) => element.dataset.scrollReveal !== "element");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!elements.length || reducedMotion.matches || !("IntersectionObserver" in window)) {
    return;
  }

  const originals = new Map(textElements.map((element) => [element, element.textContent]));
  const revealed = new WeakSet();
  function reveal(element) {
    revealed.add(element);
    element.classList.add("is-revealed");
    observer.unobserve(element);
  }
  const observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        reveal(entry.target);
      }
    }
  }, { threshold: 0.1, rootMargin: "0px 0px -24px 0px" });

  function splitLines(element) {
    const words = originals.get(element).trim().split(/\s+/);
    const fragment = document.createDocumentFragment();
    const spans = words.map((word, index) => {
      const span = document.createElement("span");
      span.textContent = word;
      fragment.append(span);
      if (index < words.length - 1) fragment.append(" ");
      return span;
    });

    element.replaceChildren(fragment);

    const lines = [];
    let previousTop;
    for (const span of spans) {
      const top = span.offsetTop;
      if (previousTop === undefined || Math.abs(top - previousTop) > 2) {
        lines.push([]);
        previousTop = top;
      }
      lines.at(-1).push(span.textContent);
    }

    element.replaceChildren(...lines.map((words, index) => {
      const line = document.createElement("span");
      line.className = "scroll-reveal-line";
      // Keep whitespace between lines for copy/paste and assistive technology.
      line.textContent = words.join(" ") + (index < lines.length - 1 ? " " : "");
      line.style.setProperty("--reveal-delay", `${index * 0.1}s`);
      return line;
    }));
    element.classList.add("scroll-reveal-ready");
  }

  for (const element of elements) {
    if (element.dataset.scrollReveal === "element") {
      const siblings = [...element.parentElement.children]
        .filter((child) => child.dataset.scrollReveal === "element");
      element.style.setProperty("--reveal-delay", `${Math.min(siblings.indexOf(element), 3) * 0.1}s`);
      element.classList.add("scroll-reveal-ready");
      // Keyboard users can reveal controls immediately by focusing them.
      element.addEventListener("focusin", () => reveal(element), { once: true });
    } else {
      splitLines(element);
    }
    observer.observe(element);
  }

  let width = window.innerWidth;
  let resizeTimer;
  function handleResize() {
    if (width === window.innerWidth) return;
    width = window.innerWidth;
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      for (const element of textElements) {
        splitLines(element);
        if (revealed.has(element)) element.classList.add("is-revealed");
      }
    }, 150);
  }

  function disableMotion(event) {
    if (!event.matches) return;
    observer.disconnect();
    window.clearTimeout(resizeTimer);
    window.removeEventListener("resize", handleResize);
    for (const element of elements) {
      if (originals.has(element)) element.textContent = originals.get(element);
      element.classList.remove("scroll-reveal-ready", "is-revealed");
    }
    reducedMotion.removeEventListener("change", disableMotion);
  }

  window.addEventListener("resize", handleResize);
  reducedMotion.addEventListener("change", disableMotion);
}
