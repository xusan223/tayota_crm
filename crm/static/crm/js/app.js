"use strict";

const tabLabels = {
  dashboard: "Dashboard",
  kanban: "Sotuv voronkasi",
  customers: "Mijozlar",
  inventory: "Avto ombori",
  kpi: "KPI ko‘rsatkichlari",
};

const panels = document.querySelectorAll(".tab-panel");
const tabs = document.querySelectorAll(".nav-tab");
const modal = document.querySelector("#lead-modal");

function switchTab(name) {
  if (!tabLabels[name]) return;

  panels.forEach((panel) => {
    panel.classList.toggle("hidden", panel.id !== `panel-${name}`);
  });

  tabs.forEach((tab) => {
    const active = tab.dataset.tab === name;
    tab.classList.toggle("bg-toyota", active);
    tab.classList.toggle("text-white/70", !active);
    tab.classList.toggle("hover:bg-white/10", !active);
  });

  document.querySelector("#page-title").textContent = tabLabels[name];
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

tabs.forEach((tab) => {
  tab.addEventListener("click", () => switchTab(tab.dataset.tab));
});

document.querySelectorAll("[data-switch-tab]").forEach((button) => {
  button.addEventListener("click", () => switchTab(button.dataset.switchTab));
});

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
