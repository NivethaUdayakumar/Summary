let monitorsTable = null;
let trackerTable = null;
let selectedMonitor = null;
let trackerPrimaryKey = "";
let trackerColumns = [];
let autoRefreshHandle = null;
let trackerViewMode = "visible"; // visible | hidden

document.addEventListener("DOMContentLoaded", async function () {
    try {
        await loadProjects();
        await loadTemplates();
        bindEvents();
        await refreshMonitors();
    } catch (err) {
        showMessage(err.message || "Failed to initialize Monitor page", "negative");
        console.error(err);
    }

    autoRefreshHandle = setInterval(async () => {
        try {
            await refreshMonitors(false);
            if (selectedMonitor) {
                await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
            }
        } catch (err) {
            console.error(err);
        }
    }, 5000);
});

function bindEvents() {
    document.getElementById("create_monitor_btn").addEventListener("click", createMonitor);

    document.getElementById("refresh_monitors_btn").addEventListener("click", async () => {
        await refreshMonitors();
        await loadTrackerFromCurrentSelection();
    });

    document.getElementById("project_select").addEventListener("change", async () => {
        trackerViewMode = "visible";
        await refreshMonitors();
        await loadTrackerFromCurrentSelection();
    });

    document.getElementById("template_select").addEventListener("change", async () => {
        trackerViewMode = "visible";
        await loadTrackerFromCurrentSelection();
    });

    document.getElementById("hide_runs_btn").addEventListener("click", async () => {
        await handleRunAction("hide");
    });

    document.getElementById("unhide_runs_btn").addEventListener("click", async () => {
        await handleUnhideFlow();
    });

    document.getElementById("update_runs_btn").addEventListener("click", async () => {
        await handleUpdateRuns();
    });
}

async function apiGet(url) {
    const res = await fetch(url);
    const data = await res.json();

    if (!res.ok || data.ok === false) {
        throw new Error(data.error || "Request failed");
    }

    return data;
}

async function apiPost(url, payload) {
    const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok || data.ok === false) {
        throw new Error(data.error || "Request failed");
    }

    return data;
}

function showMessage(text, kind = "info") {
    const box = document.getElementById("message_box");
    if (!box) return;

    box.className = `ui message ${kind}`;
    box.textContent = text;
    box.classList.remove("hidden");

    setTimeout(() => {
        box.classList.add("hidden");
    }, 3000);
}

async function loadProjects() {
    const data = await apiGet("/api/monitor/projects");
    const select = document.getElementById("project_select");
    select.innerHTML = "";

    for (const project of data.projects || []) {
        const opt = document.createElement("option");
        opt.value = project;
        opt.textContent = project;
        select.appendChild(opt);
    }
}

async function loadTemplates() {
    const data = await apiGet("/api/monitor/templates");
    const select = document.getElementById("template_select");
    select.innerHTML = "";

    for (const item of data.templates || []) {
        const opt = document.createElement("option");
        opt.value = item.template_name;
        opt.textContent = item.template_name;
        opt.dataset.has_hide_runs = item.has_hide_runs ? "1" : "0";
        opt.dataset.has_update_run = item.has_update_run ? "1" : "0";
        select.appendChild(opt);
    }
}

function getCurrentProject() {
    return document.getElementById("project_select").value;
}

function getCurrentTemplate() {
    return document.getElementById("template_select").value;
}

async function createMonitor() {
    const project_code = getCurrentProject();
    const template_name = getCurrentTemplate();

    if (!project_code || !template_name) {
        showMessage("Select project and template", "warning");
        return;
    }

    try {
        await apiPost("/api/monitor/create", { project_code, template_name });
        showMessage(`Created ${project_code}_${template_name}`, "positive");
        await refreshMonitors();
    } catch (err) {
        showMessage(err.message, "negative");
    }
}

async function refreshMonitors(resetSelection = false) {
    const project = getCurrentProject();
    const url = project
        ? `/api/monitor/list?project_code=${encodeURIComponent(project)}`
        : "/api/monitor/list";

    try {
        const data = await apiGet(url);
        renderMonitorsTable(data.rows || []);

        if (resetSelection) {
            selectedMonitor = null;
            updateSelectedMonitorLabel();
        } else if (selectedMonitor) {
            const updated = (data.rows || []).find(r => r.monitor_name === selectedMonitor.monitor_name);
            if (updated) {
                selectedMonitor = updated;
            }
            updateSelectedMonitorLabel();
        }
    } catch (err) {
        showMessage(err.message, "negative");
    }
}

function renderMonitorsTable(rows) {
    const tableId = "#monitors_table";

    if ($.fn.DataTable.isDataTable(tableId)) {
        $(tableId).DataTable().destroy();
        $(tableId + " tbody").empty();
    }

    const tbody = document.querySelector("#monitors_table tbody");
    tbody.innerHTML = "";

    rows.forEach((row) => {
        const tr = document.createElement("tr");
        tr.dataset.monitor_name = row.monitor_name;
        tr.innerHTML = `
            <td>${escapeHtml(row.monitor_name)}</td>
            <td>${escapeHtml(row.project_code)}</td>
            <td>${escapeHtml(row.template_name)}</td>
            <td>${escapeHtml(row.status)}</td>
            <td>${escapeHtml(String(row.pid || ""))}</td>
            <td>${escapeHtml(String(row.cpu_percent || 0))}</td>
            <td>${escapeHtml(String(row.memory_mb || 0))}</td>
            <td>${escapeHtml(row.last_log_timestamp || "")}</td>
            <td title="${escapeHtml(row.last_log_message || "")}">${escapeHtml(row.last_log_message || "")}</td>
            <td>
                <div class="monitor_action_btns">
                    <button class="ui mini primary button start_btn" data_name="${escapeHtml(row.monitor_name)}">Start</button>
                    <button class="ui mini button restart_btn" data_name="${escapeHtml(row.monitor_name)}">Restart</button>
                    <button class="ui mini red button terminate_btn" data_name="${escapeHtml(row.monitor_name)}">Terminate</button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });

    monitorsTable = $(tableId).DataTable({
        pageLength: 10,
        order: [[1, "asc"]],
        autoWidth: false,
        scrollX: true,
        orderMulti: true,
        searching: true,
        info: true,
        lengthChange: true,
        stateSave: true
    });

    bindMonitorRowEvents(rows);
}

function bindMonitorRowEvents(rows) {
    $("#monitors_table tbody").off("click", "tr");
    $("#monitors_table tbody").on("click", "tr", async function (e) {
        if ($(e.target).closest("button").length) {
            return;
        }

        $("#monitors_table tbody tr").removeClass("row_selected");
        $(this).addClass("row_selected");

        const monitor_name = this.dataset.monitor_name;
        const row = rows.find(r => r.monitor_name === monitor_name);
        if (!row) return;

        selectedMonitor = row;
        trackerViewMode = "visible";
        updateSelectedMonitorLabel();
        await loadTrackerTable(row.project_code, row.template_name);
    });

    $("#monitors_table tbody").off("click", ".start_btn");
    $("#monitors_table tbody").on("click", ".start_btn", async function () {
        const monitor_name = this.getAttribute("data_name");
        try {
            await apiPost("/api/monitor/start", { monitor_name });
            showMessage(`Started ${monitor_name}`, "positive");
            await refreshMonitors();
        } catch (err) {
            showMessage(err.message, "negative");
        }
    });

    $("#monitors_table tbody").off("click", ".restart_btn");
    $("#monitors_table tbody").on("click", ".restart_btn", async function () {
        const monitor_name = this.getAttribute("data_name");
        try {
            await apiPost("/api/monitor/restart", { monitor_name });
            showMessage(`Restarted ${monitor_name}`, "positive");
            await refreshMonitors();
        } catch (err) {
            showMessage(err.message, "negative");
        }
    });

    $("#monitors_table tbody").off("click", ".terminate_btn");
    $("#monitors_table tbody").on("click", ".terminate_btn", async function () {
        const monitor_name = this.getAttribute("data_name");
        try {
            await apiPost("/api/monitor/terminate", { monitor_name });
            if (selectedMonitor && selectedMonitor.monitor_name === monitor_name) {
                selectedMonitor = null;
                trackerViewMode = "visible";
                updateSelectedMonitorLabel();
                clearTrackerTable();
            }
            showMessage(`Terminated ${monitor_name}`, "positive");
            await refreshMonitors();
        } catch (err) {
            showMessage(err.message, "negative");
        }
    });
}

function updateSelectedMonitorLabel() {
    const label = document.getElementById("selected_monitor_label");
    if (!label) return;

    if (!selectedMonitor) {
        label.textContent = "No monitor selected";
        return;
    }

    const modeText = trackerViewMode === "hidden" ? "Hidden Runs View" : "Visible Runs View";
    label.textContent = `Selected: ${selectedMonitor.monitor_name} | ${modeText}`;
}

async function loadTrackerFromCurrentSelection() {
    if (selectedMonitor) {
        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
        return;
    }

    const project_code = getCurrentProject();
    const template_name = getCurrentTemplate();

    if (!project_code || !template_name) {
        clearTrackerTable();
        return;
    }

    await loadTrackerTable(project_code, template_name);
}

async function loadTrackerTable(project_code, template_name) {
    try {
        const include_hidden = trackerViewMode === "hidden" ? "1" : "0";
        const data = await apiGet(
            `/api/monitor/tracker?project_code=${encodeURIComponent(project_code)}&template_name=${encodeURIComponent(template_name)}&include_hidden=${include_hidden}`
        );

        const payload = data.data || {};
        trackerPrimaryKey = payload.primary_key || "";
        trackerColumns = payload.columns || [];

        let rows = payload.rows || [];
        rows = filterRowsForCurrentMode(rows);

        renderTrackerTable(payload.columns || [], rows, project_code, template_name);
    } catch (err) {
        clearTrackerTable();
        showMessage(err.message, "negative");
    }
}

function filterRowsForCurrentMode(rows) {
    if (!Array.isArray(rows)) return [];

    if (trackerViewMode === "hidden") {
        return rows.filter(row => Number(row.hidden || 0) === 1);
    }

    return rows.filter(row => Number(row.hidden || 0) === 0);
}

function clearTrackerTable() {
    if ($.fn.DataTable.isDataTable("#tracker_table")) {
        $("#tracker_table").DataTable().destroy();
    }

    const thead = document.querySelector("#tracker_table thead");
    const tbody = document.querySelector("#tracker_table tbody");
    const meta = document.getElementById("tracker_meta");

    if (thead) thead.innerHTML = "";
    if (tbody) tbody.innerHTML = "";
    if (meta) meta.textContent = "";
}

function renderTrackerTable(columns, rows, project_code, template_name) {
    clearTrackerTable();

    const thead = document.querySelector("#tracker_table thead");
    const tbody = document.querySelector("#tracker_table tbody");

    const headerRow = document.createElement("tr");
    const checkboxTh = document.createElement("th");
    checkboxTh.textContent = "Select";
    headerRow.appendChild(checkboxTh);

    columns.forEach(col => {
        const th = document.createElement("th");
        th.textContent = col;
        headerRow.appendChild(th);
    });

    thead.appendChild(headerRow);

    rows.forEach((row, index) => {
        const tr = document.createElement("tr");
        const pkValue = row[trackerPrimaryKey] ?? row[columns[0]] ?? index;

        let html = `<td><input type="checkbox" class="tracker_checkbox" data_run_id="${escapeHtml(String(pkValue))}"></td>`;

        columns.forEach(col => {
            const value = row[col] == null ? "" : String(row[col]);
            html += `<td title="${escapeHtml(value)}">${escapeHtml(value)}</td>`;
        });

        tr.innerHTML = html;
        tbody.appendChild(tr);
    });

    trackerTable = $("#tracker_table").DataTable({
        pageLength: 10,
        order: [[1, "asc"]],
        autoWidth: false,
        scrollX: true,
        orderMulti: true,
        searching: true,
        info: true,
        lengthChange: true,
        stateSave: true
    });

    const modeLabel = trackerViewMode === "hidden" ? "hidden only" : "visible only";

    document.getElementById("tracker_meta").textContent =
        `Project: ${project_code} | Template: ${template_name} | Table: ${template_name}_Tracker | Key: ${trackerPrimaryKey} | View: ${modeLabel}`;
}

function getSelectedRunIds() {
    const ids = [];
    document.querySelectorAll(".tracker_checkbox:checked").forEach(cb => {
        ids.push(cb.getAttribute("data_run_id"));
    });
    return ids;
}

async function handleRunAction(action) {
    const run_ids = getSelectedRunIds();

    if (!selectedMonitor) {
        showMessage("Select a monitor row first", "warning");
        return;
    }

    if (!run_ids.length) {
        showMessage("Select tracker rows first", "warning");
        return;
    }

    try {
        await apiPost("/api/monitor/hide_runs", {
            project_code: selectedMonitor.project_code,
            template_name: selectedMonitor.template_name,
            run_ids,
            action
        });

        showMessage(`${action} completed`, "positive");

        if (action === "hide") {
            trackerViewMode = "visible";
        }

        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
    } catch (err) {
        showMessage(err.message, "negative");
    }
}

async function handleUnhideFlow() {
    if (!selectedMonitor) {
        showMessage("Select a monitor row first", "warning");
        return;
    }

    const run_ids = getSelectedRunIds();

    if (!run_ids.length) {
        trackerViewMode = "hidden";
        updateSelectedMonitorLabel();
        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
        showMessage("Hidden runs loaded. Select rows to unhide.", "info");
        return;
    }

    try {
        await apiPost("/api/monitor/hide_runs", {
            project_code: selectedMonitor.project_code,
            template_name: selectedMonitor.template_name,
            run_ids,
            action: "unhide"
        });

        showMessage("unhide completed", "positive");
        trackerViewMode = "visible";
        updateSelectedMonitorLabel();
        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
    } catch (err) {
        showMessage(err.message, "negative");
    }
}

async function handleUpdateRuns() {
    const run_ids = getSelectedRunIds();

    if (!selectedMonitor) {
        showMessage("Select a monitor row first", "warning");
        return;
    }

    if (!run_ids.length) {
        showMessage("Select tracker rows first", "warning");
        return;
    }

    try {
        await apiPost("/api/monitor/update_runs", {
            project_code: selectedMonitor.project_code,
            template_name: selectedMonitor.template_name,
            run_ids
        });

        showMessage("Update run completed", "positive");
        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
    } catch (err) {
        showMessage(err.message, "negative");
    }
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}