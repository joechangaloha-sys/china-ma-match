const exchange = document.querySelector(".dispatch");
const replay = exchange.querySelector(".replay");
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

function animateExchange() {
  if (reducedMotion.matches) return;
  exchange.classList.remove("playing");
  // Start a new CSS animation even when the previous one has finished.
  void exchange.offsetWidth;
  exchange.classList.add("playing");
}

function syncMotionPreference() {
  replay.hidden = reducedMotion.matches;
}

syncMotionPreference();
reducedMotion.addEventListener("change", syncMotionPreference);
replay.addEventListener("click", animateExchange);
if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(entries => {
    if (entries.some(entry => entry.isIntersecting)) {
      animateExchange();
      observer.disconnect();
    }
  }, { threshold: 0.5 });
  observer.observe(exchange);
}
