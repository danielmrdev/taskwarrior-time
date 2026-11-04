const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function createTranslator(systemLocale) {
  const context = { Qt: { locale: () => systemLocale } };
  vm.createContext(context);
  vm.runInContext(
    fs.readFileSync(path.join(__dirname, "..", "i18n.js"), "utf8"),
    context,
  );
  return (key, locale, language) => context.t(key, locale, language);
}

const translate = createTranslator({ name: "en_US", uiLanguages: ["en_US"] });

test("Spanish override translates UI strings regardless of system locale", () => {
  assert.equal(translate("addSection", "en_US", "es"), "Nueva tarea");
  assert.equal(translate("cancel", "en_US", "es"), "Cancelar");
  assert.equal(translate("uiLanguageEs", "en_US", "es"), "Español");
});

test("system Spanish locale selects Spanish translations", () => {
  assert.equal(translate("addSection", "es-ES", "system"), "Nueva tarea");
  assert.equal(translate("uiLanguage", "es_ES.UTF-8", "system"), "Idioma de la interfaz");
});

test("Qt Spanish UI language is used when no locale is passed", () => {
  const systemTranslate = createTranslator({ name: "en_US", uiLanguages: ["es-ES"] });
  assert.equal(systemTranslate("addSection", "", "system"), "Nueva tarea");
});

test("preferred English UI language beats Spanish formatting locale", () => {
  const systemTranslate = createTranslator({ name: "es_ES", uiLanguages: ["en-US"] });
  assert.equal(systemTranslate("addSection", "en-US", "system"), "New task");
});

test("English and Spanish overrides remain available", () => {
  assert.equal(translate("addSection", "es-ES", "en"), "New task");
  assert.equal(translate("addSection", "en-US", "es"), "Nueva tarea");
});

test("unsupported Russian system locale falls back to English", () => {
  const russianTranslate = createTranslator({ name: "ru_RU", uiLanguages: ["ru-RU"] });
  assert.equal(russianTranslate("addSection", "ru_RU", "system"), "New task");
});

test("notification and alert-count strings are translated in English and Spanish", () => {
  const expected = {
    notificationTitle: ["Task reminder", "Recordatorio de tarea"],
    notificationOverdue: ["Overdue", "Vencida"],
    notificationUpcoming: ["Due within 24 hours", "Vence en las próximas 24 horas"],
    notificationNewRecurrence: ["New recurring task", "Nueva tarea recurrente"],
    tooltipAlertOverdue: ["%1 overdue alerts", "%1 alertas de tareas vencidas"],
    tooltipAlertUpcoming: ["%1 due soon", "%1 próximas a vencer"],
    tooltipAlertNewRecurrences: ["%1 new occurrences", "%1 nuevas tareas recurrentes"],
  };
  for (const [key, values] of Object.entries(expected)) {
    assert.equal(translate(key, "en_US", "en"), values[0], `${key} English`);
    assert.equal(translate(key, "es_ES", "es"), values[1], `${key} Spanish`);
  }
});

test("recurrence controls and guidance are translated in English and Spanish", () => {
  const expected = {
    recurrence: ["Recurrence", "Repetición"],
    recurrenceHint: ["Native Taskwarrior interval, e.g. 2w or 3d", "Intervalo nativo de Taskwarrior, p. ej. 2w o 3d"],
    recurrenceDueRequired: ["Recurring tasks require a due date.", "Las tareas recurrentes necesitan una fecha límite."],
    stopSeries: ["Stop series", "Detener serie"],
    stopSeriesConfirm: ["Stop this recurring series? Existing occurrences will remain.", "¿Detener esta serie recurrente? Las tareas ya generadas se conservarán."],
    recurrenceClearGuidance: ["Use Stop series to end recurrence.", "Usa «Detener serie» para finalizar la repetición."],
    statusRecurring: ["Recurring template", "Plantilla recurrente"],
  };
  for (const [key, values] of Object.entries(expected)) {
    assert.equal(translate(key, "en_US", "en"), values[0], `${key} English`);
    assert.equal(translate(key, "es_ES", "es"), values[1], `${key} Spanish`);
  }
});
