"use strict";

const tabLabels = {
  dashboard: "Dashboard",
  kanban: "Sotuv voronkasi",
  customers: "Mijozlar",
  tasks: "Vazifalar",
  inventory: "Avto ombori",
  kpi: "KPI ko‘rsatkichlari",
};

const panels = document.querySelectorAll(".tab-panel");
const tabs = document.querySelectorAll(".nav-tab");
const modal = document.querySelector("#lead-modal");
const onDashboard = panels.length > 0;

function hasPanel(name) {
  return Boolean(tabLabels[name] && document.querySelector(`#panel-${name}`));
}

function highlightTab(name) {
  tabs.forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("bg-toyota", active);
    tab.classList.toggle("text-white", active);
    tab.classList.toggle("text-white/70", !active);
    tab.classList.toggle("hover:bg-white/10", !active);
    if (active) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  });
}

function switchTab(name, { updateHash = true } = {}) {
  if (!hasPanel(name)) return;

  panels.forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `panel-${name}`);
  });
  highlightTab(name);
  document.querySelector("#page-title").textContent = tabLabels[name];
  if (updateHash) history.replaceState(null, "", `${location.pathname}${location.search}#${name}`);
}

function initialTab() {
  const fromHash = location.hash.slice(1);
  if (hasPanel(fromHash)) return fromHash;
  if (new URLSearchParams(location.search).has("q")) return "customers";
  return "dashboard";
}

function openModal() {
  modal.classList.remove("hidden");
  modal.classList.add("flex");
  document.querySelector("#name").focus();
}

function closeModal() {
  modal.classList.add("hidden");
  modal.classList.remove("flex");
}

if (onDashboard) {
  tabs.forEach((tab) => {
    tab.addEventListener("click", (event) => {
      event.preventDefault();
      switchTab(tab.dataset.tab);
    });
  });

  document.querySelectorAll("[data-switch-tab]").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.switchTab));
  });

  window.addEventListener("hashchange", () => switchTab(location.hash.slice(1), { updateHash: false }));
  switchTab(initialTab(), { updateHash: false });
}

document.querySelectorAll("[data-open-modal]").forEach((button) => {
  button.addEventListener("click", openModal);
});

document.querySelectorAll("[data-close-modal]").forEach((button) => {
  button.addEventListener("click", closeModal);
});

modal.addEventListener("click", (event) => {
  if (event.target === modal) closeModal();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !modal.classList.contains("hidden")) closeModal();
});
