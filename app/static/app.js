const LANGUAGE_STORAGE_KEY = "boardsesh-crux-language";

const translations = {
  en: {
    catalogConverter: "MoonBoard catalog converter",
    heroDescription: "Create a CRUX import file from the public BoardSesh snapshot and a persistent MoonBoard mapping from CRUX WLED Bridge.",
    loadMapping: "Load mapping",
    mappingSourceHelp: "Directly from the bridge or from a previously exported JSON file.",
    bridgeUrl: "Bridge URL",
    wallId: "CRUX wall ID",
    loadMappings: "Load mappings from bridge",
    or: "or",
    openMappingJson: "Open mapping JSON",
    persistentMapping: "Persistent MoonBoard mapping",
    loadMappingsFirst: "Load mappings first …",
    configureExport: "Configure export",
    mappingProvidesBoard: "Board and setup come from the selected mapping.",
    wallAngle: "Wall angle",
    allAngles: "All angles in snapshot",
    gradeScale: "Grade scale",
    vScale: "V scale",
    footRuleHint: "The foot rule is derived from the BoardSesh characteristics for each climb. “Footless + kickboard” is skipped because CRUX has no exact equivalent.",
    createImport: "Create CRUX import file",
    exportFinePrint: "The current BoardSesh snapshot is downloaded and cached locally on the first export. Climbs with missing hold mappings are skipped and recorded in the file.",
    schemaLink: "Import format JSON Schema",
    dataSource: "BoardSesh data source",
    switchToGerman: "Switch to German",
    switchToEnglish: "Switch to English",
    mappingJsonRequired: "The mapping file must contain JSON.",
    noPersistentMapping: "No persistent MoonBoard mapping found.",
    unnamedMapping: "Unnamed mapping",
    noMappings: "No mappings found",
    wall: "Wall",
    board: "Board",
    setup: "Setup",
    boardseshLayoutId: "BoardSesh layout ID",
    cruxWallId: "CRUX wall ID",
    enterBridgeDetails: "Enter the bridge URL and CRUX wall ID.",
    loadingMappings: "Loading persistent mappings from the bridge …",
    mappingsLoaded: "{count} mapping(s) loaded.",
    mappingsLoadedFromFile: "{count} mapping(s) loaded from {filename}.",
    selectMappingFirst: "Load and select a mapping first.",
    converting: "Loading BoardSesh snapshot and converting …",
    climbsExported: "{count} climbs exported · {filename}",
    importDownloaded: "The import file was created and downloaded."
  },
  de: {
    catalogConverter: "MoonBoard-Katalogkonverter",
    heroDescription: "Erzeuge eine CRUX-Importdatei aus dem öffentlichen BoardSesh-Snapshot und einem persistenten MoonBoard-Mapping aus der CRUX WLED Bridge.",
    loadMapping: "Mapping laden",
    mappingSourceHelp: "Direkt von der Bridge oder als zuvor exportierte JSON-Datei.",
    bridgeUrl: "Bridge-URL",
    wallId: "CRUX Wall-ID",
    loadMappings: "Mappings von Bridge laden",
    or: "oder",
    openMappingJson: "Mapping-JSON öffnen",
    persistentMapping: "Persistentes MoonBoard-Mapping",
    loadMappingsFirst: "Zuerst Mappings laden …",
    configureExport: "Export einstellen",
    mappingProvidesBoard: "Board und Setup kommen aus dem ausgewählten Mapping.",
    wallAngle: "Wandwinkel",
    allAngles: "Alle im Snapshot",
    gradeScale: "Gradskala",
    vScale: "V-Skala",
    footRuleHint: "Die Fußregel wird für jeden Boulder aus den BoardSesh-Characteristics abgeleitet. „Footless + kickboard“ wird übersprungen, weil CRUX dafür keine exakt passende Fußregel hat.",
    createImport: "CRUX-Importdatei erzeugen",
    exportFinePrint: "Beim ersten Export wird der aktuelle BoardSesh-Snapshot geladen und lokal gecacht. Boulder mit fehlenden Hold-Zuordnungen werden übersprungen und in der Datei protokolliert.",
    schemaLink: "JSON-Schema des Importformats",
    dataSource: "BoardSesh-Datenquelle",
    switchToGerman: "Auf Deutsch wechseln",
    switchToEnglish: "Auf Englisch wechseln",
    mappingJsonRequired: "Die Mapping-Datei muss JSON enthalten.",
    noPersistentMapping: "Kein persistentes MoonBoard-Mapping gefunden.",
    unnamedMapping: "Unbenanntes Mapping",
    noMappings: "Keine Mappings gefunden",
    wall: "Wall",
    board: "Board",
    setup: "Setup",
    boardseshLayoutId: "BoardSesh Layout-ID",
    cruxWallId: "CRUX Wall-ID",
    enterBridgeDetails: "Bitte Bridge-URL und CRUX Wall-ID eingeben.",
    loadingMappings: "Lade persistente Mappings von der Bridge …",
    mappingsLoaded: "{count} Mapping(s) geladen.",
    mappingsLoadedFromFile: "{count} Mapping(s) aus {filename} geladen.",
    selectMappingFirst: "Bitte zuerst ein Mapping laden und auswählen.",
    converting: "Lade BoardSesh-Snapshot und konvertiere …",
    climbsExported: "{count} Boulder exportiert · {filename}",
    importDownloaded: "Importdatei wurde erzeugt und heruntergeladen."
  }
};

const form = document.querySelector("#converter-form");
const bridgeUrl = document.querySelector("#bridge-url");
const wallId = document.querySelector("#wall-id");
const loadBridge = document.querySelector("#load-bridge");
const mappingFile = document.querySelector("#mapping-file");
const mappingSelect = document.querySelector("#mapping-select");
const mappingInfo = document.querySelector("#mapping-info");
const statusBox = document.querySelector("#status");
const resultBox = document.querySelector("#result");
const convertButton = document.querySelector("#convert");
const languageToggle = document.querySelector("#language-toggle");
const languageFlag = document.querySelector("#language-flag");

let currentLanguage = "en";
let uploadedPayload = null;
let summaries = [];
let statusState = null;
let resultState = null;

function t(key, variables = {}) {
  const template = translations[currentLanguage][key] || translations.en[key] || key;
  return template.replace(/\{(\w+)\}/g, (_, name) => String(variables[name] ?? ""));
}

function storedLanguage() {
  try {
    return localStorage.getItem(LANGUAGE_STORAGE_KEY) === "de" ? "de" : "en";
  } catch {
    return "en";
  }
}

function saveLanguage(language) {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // The language still changes for this page if storage is unavailable.
  }
}

function renderStatus() {
  if (!statusState) return;
  statusBox.textContent = statusState.key
    ? t(statusState.key, statusState.variables)
    : statusState.message;
  statusBox.className = ("status " + statusState.kind).trim();
}

function setTranslatedStatus(key, variables = {}, kind = "") {
  statusState = {key, variables, kind};
  renderStatus();
}

function setRawStatus(message, kind = "") {
  statusState = {message, kind};
  renderStatus();
}

function renderResult() {
  if (!resultState) return;
  resultBox.textContent = t("climbsExported", resultState);
}

function applyLanguage(language, persist = false) {
  currentLanguage = language === "de" ? "de" : "en";
  document.documentElement.lang = currentLanguage;

  for (const element of document.querySelectorAll("[data-i18n]")) {
    element.textContent = t(element.dataset.i18n);
  }

  const switchKey = currentLanguage === "en" ? "switchToGerman" : "switchToEnglish";
  const switchLabel = t(switchKey);
  languageFlag.textContent = currentLanguage === "en" ? "🇩🇪" : "🇬🇧";
  languageToggle.setAttribute("aria-label", switchLabel);
  languageToggle.title = switchLabel;

  if (persist) saveLanguage(currentLanguage);

  if (summaries.length) {
    showMappings(summaries, mappingSelect.value);
  } else if (mappingSelect.dataset.state === "empty") {
    mappingSelect.replaceChildren(new Option(t("noMappings"), ""));
  }
  renderStatus();
  renderResult();
}

function errorMessage(error) {
  if (error instanceof Error) return error.message;
  return String(error);
}

async function responseError(response) {
  try {
    const payload = await response.json();
    return payload.detail || JSON.stringify(payload);
  } catch {
    return "HTTP " + response.status;
  }
}

function recordsFromPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") {
    throw new Error(t("mappingJsonRequired"));
  }
  if (Array.isArray(payload.mappings)) return payload.mappings;
  if (payload.mapping && typeof payload.mapping === "object" && "wallid" in payload.mapping) {
    return [payload.mapping];
  }
  if ("wallid" in payload && payload.mapping && typeof payload.mapping === "object") {
    return [payload];
  }
  throw new Error(t("noPersistentMapping"));
}

function summarizePayload(payload) {
  return recordsFromPayload(payload).map((record) => ({
    id: String(record.id || ""),
    name: record.name ? String(record.name) : "",
    wallid: record.wallid,
    board_type: record.board_type || "",
    setup: record.setup || "",
    boardsesh_layout_id: record.mapping?.boardsesh_layout_id,
  }));
}

function showMappings(items, selectedId = mappingSelect.value) {
  summaries = items;
  mappingSelect.replaceChildren();

  if (!items.length) {
    mappingSelect.dataset.state = "empty";
    mappingSelect.disabled = true;
    mappingSelect.append(new Option(t("noMappings"), ""));
    mappingInfo.textContent = "";
    return;
  }

  mappingSelect.dataset.state = "loaded";
  for (const item of items) {
    const board = [item.board_type, item.setup].filter(Boolean).join(" / ");
    const label = [
      item.name || t("unnamedMapping"),
      board,
      t("wall") + " " + item.wallid,
    ].filter(Boolean).join(" — ");
    mappingSelect.append(new Option(label, item.id));
  }
  mappingSelect.disabled = false;
  if (selectedId && items.some((item) => item.id === selectedId)) {
    mappingSelect.value = selectedId;
  } else {
    mappingSelect.selectedIndex = 0;
  }
  showSelectedMapping();
}

function showSelectedMapping() {
  const selected = summaries.find((item) => item.id === mappingSelect.value) || summaries[0];
  if (!selected) {
    mappingInfo.textContent = "";
    return;
  }
  mappingInfo.textContent =
    t("board") + ": " + (selected.board_type || "–") +
    " · " + t("setup") + ": " + (selected.setup || "–") +
    " · " + t("boardseshLayoutId") + ": " + (selected.boardsesh_layout_id ?? "–") +
    " · " + t("cruxWallId") + ": " + (selected.wallid ?? "–");
}

languageToggle.addEventListener("click", () => {
  applyLanguage(currentLanguage === "en" ? "de" : "en", true);
});

loadBridge.addEventListener("click", async () => {
  const url = bridgeUrl.value.trim();
  const wall = Number(wallId.value);
  if (!url || !Number.isInteger(wall) || wall <= 0) {
    setTranslatedStatus("enterBridgeDetails", {}, "error");
    return;
  }

  uploadedPayload = null;
  loadBridge.disabled = true;
  setTranslatedStatus("loadingMappings", {}, "busy");
  try {
    const response = await fetch("/api/bridge/mappings", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({bridge_url: url, wall_id: wall}),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const payload = await response.json();
    showMappings(payload.mappings);
    setTranslatedStatus("mappingsLoaded", {count: payload.mappings.length}, "success");
  } catch (error) {
    showMappings([]);
    setRawStatus(errorMessage(error), "error");
  } finally {
    loadBridge.disabled = false;
  }
});

mappingFile.addEventListener("change", async () => {
  const file = mappingFile.files?.[0];
  if (!file) return;

  try {
    uploadedPayload = JSON.parse(await file.text());
    const items = summarizePayload(uploadedPayload);
    showMappings(items);
    setTranslatedStatus(
      "mappingsLoadedFromFile",
      {count: items.length, filename: file.name},
      "success",
    );
  } catch (error) {
    uploadedPayload = null;
    showMappings([]);
    setRawStatus(errorMessage(error), "error");
  }
});

mappingSelect.addEventListener("change", showSelectedMapping);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (mappingSelect.disabled || !summaries.length) {
    setTranslatedStatus("selectMappingFirst", {}, "error");
    return;
  }

  const angleValue = document.querySelector("#angle").value;
  const request = {
    mapping_id: mappingSelect.value || null,
    angle: angleValue ? Number(angleValue) : null,
    grade_system: document.querySelector("#grade-system").value,
  };

  if (uploadedPayload) {
    request.mapping_payload = uploadedPayload;
  } else {
    request.bridge_url = bridgeUrl.value.trim();
    request.wall_id = Number(wallId.value);
  }

  convertButton.disabled = true;
  resultBox.hidden = true;
  resultState = null;
  setTranslatedStatus("converting", {}, "busy");

  try {
    const response = await fetch("/api/convert", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(request),
    });
    if (!response.ok) throw new Error(await responseError(response));

    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || "crux-import.json";
    const included = response.headers.get("X-Included-Climbs") || "?";
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(downloadUrl);

    resultState = {count: included, filename};
    resultBox.hidden = false;
    renderResult();
    setTranslatedStatus("importDownloaded", {}, "success");
  } catch (error) {
    setRawStatus(errorMessage(error), "error");
  } finally {
    convertButton.disabled = false;
  }
});

applyLanguage(storedLanguage());
