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

let uploadedPayload = null;
let summaries = [];

function setStatus(message, kind = "") {
  statusBox.textContent = message;
  statusBox.className = ("status " + kind).trim();
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
    throw new Error("Die Mapping-Datei muss JSON enthalten.");
  }
  if (Array.isArray(payload.mappings)) return payload.mappings;
  if (payload.mapping && typeof payload.mapping === "object" && "wallid" in payload.mapping) {
    return [payload.mapping];
  }
  if ("wallid" in payload && payload.mapping && typeof payload.mapping === "object") {
    return [payload];
  }
  throw new Error("Kein persistentes MoonBoard-Mapping gefunden.");
}

function summarizePayload(payload) {
  return recordsFromPayload(payload).map((record) => ({
    id: String(record.id || ""),
    name: String(record.name || "Unbenanntes Mapping"),
    wallid: record.wallid,
    board_type: record.board_type || "",
    setup: record.setup || "",
    boardsesh_layout_id: record.mapping?.boardsesh_layout_id,
  }));
}

function showMappings(items) {
  summaries = items;
  mappingSelect.replaceChildren();

  if (!items.length) {
    mappingSelect.disabled = true;
    mappingSelect.append(new Option("Keine Mappings gefunden", ""));
    mappingInfo.textContent = "";
    return;
  }

  for (const item of items) {
    const board = [item.board_type, item.setup].filter(Boolean).join(" / ");
    const label = [item.name, board, "Wall " + item.wallid].filter(Boolean).join(" — ");
    mappingSelect.append(new Option(label, item.id));
  }
  mappingSelect.disabled = false;
  mappingSelect.selectedIndex = 0;
  showSelectedMapping();
}

function showSelectedMapping() {
  const selected = summaries.find((item) => item.id === mappingSelect.value) || summaries[0];
  if (!selected) {
    mappingInfo.textContent = "";
    return;
  }
  mappingInfo.textContent =
    "Board: " + (selected.board_type || "–") +
    " · Setup: " + (selected.setup || "–") +
    " · BoardSesh Layout-ID: " + (selected.boardsesh_layout_id ?? "–") +
    " · CRUX Wall-ID: " + (selected.wallid ?? "–");
}

loadBridge.addEventListener("click", async () => {
  const url = bridgeUrl.value.trim();
  const wall = Number(wallId.value);
  if (!url || !Number.isInteger(wall) || wall <= 0) {
    setStatus("Bitte Bridge-URL und CRUX Wall-ID eingeben.", "error");
    return;
  }

  uploadedPayload = null;
  loadBridge.disabled = true;
  setStatus("Lade persistente Mappings von der Bridge …", "busy");
  try {
    const response = await fetch("/api/bridge/mappings", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({bridge_url: url, wall_id: wall}),
    });
    if (!response.ok) throw new Error(await responseError(response));
    const payload = await response.json();
    showMappings(payload.mappings);
    setStatus(payload.mappings.length + " Mapping(s) geladen.", "success");
  } catch (error) {
    showMappings([]);
    setStatus(errorMessage(error), "error");
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
    setStatus(items.length + " Mapping(s) aus " + file.name + " geladen.", "success");
  } catch (error) {
    uploadedPayload = null;
    showMappings([]);
    setStatus(errorMessage(error), "error");
  }
});

mappingSelect.addEventListener("change", showSelectedMapping);

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (mappingSelect.disabled || !summaries.length) {
    setStatus("Bitte zuerst ein Mapping laden und auswählen.", "error");
    return;
  }

  const angleValue = document.querySelector("#angle").value;
  const request = {
    mapping_id: mappingSelect.value || null,
    angle: angleValue ? Number(angleValue) : null,
    grade_system: document.querySelector("#grade-system").value,
    foot_rules: document.querySelector("#foot-rules").value,
  };

  if (uploadedPayload) {
    request.mapping_payload = uploadedPayload;
  } else {
    request.bridge_url = bridgeUrl.value.trim();
    request.wall_id = Number(wallId.value);
  }

  convertButton.disabled = true;
  resultBox.hidden = true;
  setStatus("Lade BoardSesh-Snapshot und konvertiere …", "busy");

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

    resultBox.hidden = false;
    resultBox.textContent = included + " Boulder exportiert · " + filename;
    setStatus("Importdatei wurde erzeugt und heruntergeladen.", "success");
  } catch (error) {
    setStatus(errorMessage(error), "error");
  } finally {
    convertButton.disabled = false;
  }
});
