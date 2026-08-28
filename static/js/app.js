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
