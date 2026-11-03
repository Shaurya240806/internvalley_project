// Small progressive enhancements. The site works without JavaScript.
document.documentElement.classList.add("js");

document.addEventListener("DOMContentLoaded", () => {
  // Mobile navigation toggle
  const toggle = document.querySelector(".nav-toggle");
  const links = document.getElementById("nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  const passwordInput = document.querySelector("[data-password-meter]");
  const meterBar = document.getElementById("password-meter-bar");
  const meterText = document.getElementById("password-meter-text");

  if (passwordInput && meterBar && meterText) {
    const strengthLabels = ["weak", "fair", "good", "strong", "excellent"];

    const updateMeter = () => {
      const value = passwordInput.value;
      let score = 0;

      if (value.length >= 8) score += 1;
      if (/[A-Z]/.test(value)) score += 1;
      if (/[0-9]/.test(value)) score += 1;
      if (/[^A-Za-z0-9]/.test(value)) score += 1;

      const safeScore = Math.min(score, 4);
      const width = (safeScore / 4) * 100;
      const label = value ? strengthLabels[safeScore] : "weak";

      meterBar.style.width = `${width}%`;
      meterBar.dataset.level = label;
      meterText.textContent = `Password strength: ${label}`;
    };

    passwordInput.addEventListener("input", updateMeter);
    updateMeter();
  }

  // Fade-in on scroll
  const items = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("visible"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    items.forEach((el) => io.observe(el));
  } else {
    items.forEach((el) => el.classList.add("visible"));
  }
});
