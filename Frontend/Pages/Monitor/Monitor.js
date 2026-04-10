let monitorsTable = null;
let trackerTable = null;
let selectedMonitor = null;
let trackerColumns = [];
let trackerIdColumns = ["Job", "Milestone", "Block", "Stage"];
let autoRefreshHandle = null;
let trackerViewMode = "visible";

document.addEventListener("DOMContentLoaded", async function () {
    try {
        $(".ui.dropdown").dropdown();
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
        selectedMonitor = null;
        updateSelectedMonitorLabel();
        await refreshMonitors();
        await loadTrackerFromCurrentSelection();
    });

    document.getElementById("template_select").addEventListener("change", async () => {
        if (!selectedMonitor) {
            await loadTrackerFromCurrentSelection();
        }
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

    $(".ui.dropdown").dropdown("refresh");
}

async function loadTemplates() {
    const data = await apiGet("/api/monitor/templates");
    const select = document.getElementById("template_select");
    select.innerHTML = "";

    for (const item of data.templates || []) {
        const opt = document.createElement("option");
        opt.value = item.template_name;
        opt.textContent = item.template_name;
        select.appendChild(opt);
    }

    $(".ui.dropdown").dropdown("refresh");
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
        const rows = data.rows || [];

        renderMonitorsTable(rows);

        if (resetSelection) {
            selectedMonitor = null;
            updateSelectedMonitorLabel();
        } else if (selectedMonitor) {
            const updated = rows.find(r => r.monitor_name === selectedMonitor.monitor_name);
            if (updated) {
                selectedMonitor = updated;
            } else {
                selectedMonitor = null;
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
    $("#monitors_table tbody").on("click", ".start_btn", async function (e) {
        e.stopPropagation();
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
    $("#monitors_table tbody").on("click", ".restart_btn", async function (e) {
        e.stopPropagation();
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
    $("#monitors_table tbody").on("click", ".terminate_btn", async function (e) {
        e.stopPropagation();
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
        const data = await apiGet(
            `/api/monitor/tracker?project_code=${encodeURIComponent(project_code)}&template_name=${encodeURIComponent(template_name)}`
        );

        const payload = data.data || {};
        trackerColumns = payload.columns || [];
        trackerIdColumns = payload.id_columns || ["Job", "Milestone", "Block", "Stage"];

        let rows = payload.rows || [];
        rows = filterRowsForCurrentMode(rows);

        renderTrackerTable(
            payload.columns || [],
            rows,
            project_code,
            template_name,
            payload.table_name || `${template_name}_Tracker`
        );
    } catch (err) {
        clearTrackerTable();
        showMessage(err.message, "negative");
    }
}

function filterRowsForCurrentMode(rows) {
    if (!Array.isArray(rows)) return [];

    if (!trackerColumns.includes("Hidden")) {
        return rows;
    }

    if (trackerViewMode === "hidden") {
        return rows.filter(row => Number(row.Hidden || 0) === 1);
    }

    return rows.filter(row => Number(row.Hidden || 0) === 0);
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

function renderTrackerTable(columns, rows, project_code, template_name, tableName) {
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

    rows.forEach((row) => {
        const tr = document.createElement("tr");
        const rowIdentity = {};

        trackerIdColumns.forEach(col => {
            rowIdentity[col] = row[col] == null ? "" : String(row[col]);
        });

        let html = `<td><input type="checkbox" class="tracker_checkbox" data_run_row='${escapeHtmlAttr(JSON.stringify(rowIdentity))}'></td>`;

        columns.forEach(col => {
            const value = row[col] == null ? "" : String(row[col]);
            html += `<td title="${escapeHtmlAttr(value)}">${escapeHtml(value)}</td>`;
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
        `Project: ${project_code} | Template: ${template_name} | DB: /proj/${project_code}/DashAI/DashAI_${template_name}.db | Table: ${tableName} | Row ID: ${trackerIdColumns.join(", ")} | View: ${modeLabel}`;
}

function getSelectedRunRows() {
    const rows = [];

    document.querySelectorAll(".tracker_checkbox:checked").forEach(cb => {
        try {
            rows.push(JSON.parse(cb.getAttribute("data_run_row")));
        } catch (err) {
            console.error(err);
        }
    });

    return rows;
}

async function handleRunAction(action) {
    const run_rows = getSelectedRunRows();

    if (!selectedMonitor) {
        showMessage("Select a monitor row first", "warning");
        return;
    }

    if (!run_rows.length) {
        showMessage("Select tracker rows first", "warning");
        return;
    }

    try {
        await apiPost("/api/monitor/hide_runs", {
            project_code: selectedMonitor.project_code,
            template_name: selectedMonitor.template_name,
            run_rows,
            action
        });

        showMessage(`${action} queued`, "positive");

        if (action === "hide") {
            trackerViewMode = "visible";
        }

        updateSelectedMonitorLabel();
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

    const run_rows = getSelectedRunRows();

    if (!run_rows.length) {
        trackerViewMode = "hidden";
        updateSelectedMonitorLabel();
        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
        showMessage("Hidden runs loaded. Select rows to add back.", "info");
        return;
    }

    try {
        await apiPost("/api/monitor/hide_runs", {
            project_code: selectedMonitor.project_code,
            template_name: selectedMonitor.template_name,
            run_rows,
            action: "unhide"
        });

        showMessage("unhide queued", "positive");
        trackerViewMode = "visible";
        updateSelectedMonitorLabel();
        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
    } catch (err) {
        showMessage(err.message, "negative");
    }
}

async function handleUpdateRuns() {
    const run_rows = getSelectedRunRows();

    if (!selectedMonitor) {
        showMessage("Select a monitor row first", "warning");
        return;
    }

    if (!run_rows.length) {
        showMessage("Select tracker rows first", "warning");
        return;
    }

    try {
        await apiPost("/api/monitor/update_runs", {
            project_code: selectedMonitor.project_code,
            template_name: selectedMonitor.template_name,
            run_rows
        });

        showMessage("Update queued", "positive");
        await loadTrackerTable(selectedMonitor.project_code, selectedMonitor.template_name);
    } catch (err) {
        showMessage(err.message, "negative");
    }
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function escapeHtmlAttr(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}