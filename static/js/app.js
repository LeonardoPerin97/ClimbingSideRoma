const toggle = document.querySelector("[data-menu-toggle]");
const menu = document.querySelector("[data-menu]");

if (toggle && menu) {
  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!isOpen));
    menu.classList.toggle("is-open", !isOpen);
  });
}

const languageSelect = document.querySelector("[data-language-select]");
if (languageSelect) {
  languageSelect.addEventListener("change", () => {
    languageSelect.form?.requestSubmit();
  });
}

const projectToggle = document.querySelector("[data-project-toggle]");
const gradeField = document.querySelector("[data-grade-field]");

if (projectToggle && gradeField) {
  const syncProjectGrade = () => {
    gradeField.disabled = projectToggle.checked;
    if (projectToggle.checked) {
      gradeField.value = "";
    }
  };
  projectToggle.addEventListener("change", syncProjectGrade);
  syncProjectGrade();
}

const attemptType = document.querySelector("[data-attempt-type]");
const attemptCount = document.querySelector("[data-attempt-count]");

if (attemptType && attemptCount) {
  const syncAttemptCount = () => {
    const usesCount = attemptType.value === "count";
    attemptCount.disabled = !usesCount;
    attemptCount.closest(".form-group")?.classList.toggle("is-hidden", !usesCount);
    if (!usesCount) {
      attemptCount.value = "";
    }
  };
  attemptType.addEventListener("change", syncAttemptCount);
  syncAttemptCount();
}

document.querySelectorAll("[data-discipline-histogram]").forEach((histogram) => {
  const buttons = histogram.querySelectorAll("[data-histogram-filter]");
  const columns = Array.from(histogram.querySelectorAll(".histogram-column"));
  const maximumLabel = histogram.querySelector("[data-histogram-y-maximum]");
  const legends = histogram.querySelectorAll("[data-histogram-legend]");

  const countForMode = (column, mode) => {
    const routes = Number(column.dataset.routeCount || 0);
    const boulders = Number(column.dataset.boulderCount || 0);

    if (mode === "route") return routes;
    if (mode === "boulder") return boulders;
    return routes + boulders;
  };

  const updateHistogram = (mode) => {
    const counts = columns.map((column) => countForMode(column, mode));
    const maximum = Math.max(0, ...counts);
    const heightDenominator = Math.max(1, maximum);

    if (maximumLabel) maximumLabel.textContent = String(maximum);

    columns.forEach((column, index) => {
      const count = counts[index];
      const bar = column.querySelector("[data-histogram-bar]");
      const value = column.querySelector("[data-histogram-value]");

      if (value) value.textContent = String(count);
      if (bar) {
        bar.style.setProperty(
          "--histogram-height",
          `${(count / heightDenominator) * 100}%`,
        );
        bar.classList.toggle("is-zero", count === 0);
      }

      column.querySelectorAll("[data-histogram-segment]").forEach((segment) => {
        segment.hidden = mode !== "all" && segment.dataset.histogramSegment !== mode;
      });
    });

    buttons.forEach((button) => {
      const isActive = button.dataset.histogramFilter === mode;
      button.classList.toggle("is-active", isActive);
      button.setAttribute("aria-pressed", String(isActive));
    });

    legends.forEach((legend) => {
      legend.hidden = mode !== "all" && legend.dataset.histogramLegend !== mode;
    });
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      updateHistogram(button.dataset.histogramFilter || "all");
    });
  });
});
