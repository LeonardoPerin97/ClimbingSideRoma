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

const refreshSectionFromForm = async (form, sectionSelector, selectSelector = "") => {
  const currentSection = document.querySelector(sectionSelector);
  if (!currentSection) return;

  const requestUrl = new URL(window.location.href);
  requestUrl.search = new URLSearchParams(new FormData(form)).toString();
  const action = form.getAttribute("action") || "";
  const actionHash = action.includes("#") ? action.slice(action.indexOf("#")) : "";
  requestUrl.hash = actionHash;
  const scrollLeft = window.scrollX;
  const scrollTop = window.scrollY;
  const selectedControl = selectSelector ? form.querySelector(selectSelector) : null;
  const selectedValue = selectedControl?.value;
  const activeControl = document.activeElement;
  const activeControlId =
    activeControl instanceof HTMLElement && form.contains(activeControl)
      ? activeControl.id
      : "";

  form.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(`${requestUrl.pathname}${requestUrl.search}`, {
      headers: { Accept: "text/html" },
    });
    if (!response.ok) throw new Error("Unable to refresh filtered results.");

    const html = await response.text();
    const parsedDocument = new DOMParser().parseFromString(html, "text/html");
    const refreshedSection = parsedDocument.querySelector(sectionSelector);
    if (!refreshedSection) throw new Error("Filtered results section was not found.");

    currentSection.replaceWith(refreshedSection);
    window.history.replaceState(null, "", requestUrl.href);
    window.scrollTo({ left: scrollLeft, top: scrollTop, behavior: "auto" });

    const refreshedSelect = selectSelector
      ? refreshedSection.querySelector(selectSelector)
      : null;
    if (refreshedSelect && selectedValue) {
      refreshedSelect.value = selectedValue;
      refreshedSelect.focus({ preventScroll: true });
    } else if (activeControlId) {
      const refreshedActiveControl = refreshedSection.querySelector(`#${activeControlId}`);
      refreshedActiveControl?.focus({ preventScroll: true });
    }
  } catch (error) {
    console.error(error);
    window.location.assign(requestUrl.href);
  } finally {
    form.removeAttribute("aria-busy");
  }
};

const refreshProfileCatalogueProgress = (form) =>
  refreshSectionFromForm(form, "#profile-progress", "[data-profile-catalogue-scope]");

const refreshCommunityRanking = (form) =>
  refreshSectionFromForm(form, "#community-ranking", "[data-community-period]");

const filterRefreshTimers = new WeakMap();

const cancelPendingFilterRefresh = (form) => {
  const pendingTimer = filterRefreshTimers.get(form);
  if (!pendingTimer) return;
  window.clearTimeout(pendingTimer);
  filterRefreshTimers.delete(form);
};

const refreshAjaxFilter = (form) => {
  const target = form.dataset.filterTarget;
  if (!target) return;
  void refreshSectionFromForm(form, target);
};

const queueAjaxFilterRefresh = (form, debounce = false) => {
  cancelPendingFilterRefresh(form);

  if (debounce) {
    const timer = window.setTimeout(() => {
      filterRefreshTimers.delete(form);
      refreshAjaxFilter(form);
    }, 300);
    filterRefreshTimers.set(form, timer);
    return;
  }

  refreshAjaxFilter(form);
};

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLSelectElement) || !target.form) return;
  if (target.matches("[data-grade-filter-mode]")) {
    syncGradeFilter(target);
  }
  if (target.matches("[data-profile-catalogue-scope]")) {
    void refreshProfileCatalogueProgress(target.form);
  } else if (target.matches("[data-community-period]")) {
    void refreshCommunityRanking(target.form);
  } else if (target.form.matches("[data-ajax-filter-form]")) {
    queueAjaxFilterRefresh(target.form);
  }
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || !target.form) return;
  if (
    target.matches("[data-filter-search]") &&
    target.form.matches("[data-ajax-filter-form]")
  ) {
    queueAjaxFilterRefresh(target.form, true);
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!(form instanceof HTMLFormElement) || !form.matches("[data-ajax-filter-form]")) return;
  event.preventDefault();
  cancelPendingFilterRefresh(form);
  refreshAjaxFilter(form);
});

document.querySelectorAll("[data-confirm-logout]").forEach((form) => {
  form.addEventListener("submit", (event) => {
    const message = form.dataset.confirmLogout;
    if (message && !window.confirm(message)) {
      event.preventDefault();
    }
  });
});

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

const syncGradeFilter = (gradeFilterMode) => {
  const gradeFilterValue = gradeFilterMode.form?.querySelector("[data-grade-filter-value]");
  if (!gradeFilterValue) return;

  const showsAllGrades = gradeFilterMode.value === "all";
  gradeFilterValue.disabled = showsAllGrades;
  if (showsAllGrades) {
    gradeFilterValue.value = "";
  }
};

document.querySelectorAll("[data-grade-filter-mode]").forEach(syncGradeFilter);

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

const histogramColumns = Array.from(
  document.querySelectorAll("[data-histogram-column]"),
);

histogramColumns.forEach((column) => {
  column.addEventListener("click", () => {
    const shouldShow = !column.classList.contains("is-tooltip-visible");
    histogramColumns.forEach((item) => item.classList.remove("is-tooltip-visible"));
    column.classList.toggle("is-tooltip-visible", shouldShow);
  });
});

document.addEventListener("click", (event) => {
  if (!event.target.closest("[data-histogram-column]")) {
    histogramColumns.forEach((column) => {
      column.classList.remove("is-tooltip-visible");
    });
  }
});
