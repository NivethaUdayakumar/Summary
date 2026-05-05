const AUTO_REFRESH_MS = 5000;
let refreshHandle = null;

document.addEventListener("DOMContentLoaded", async () => {
    bindEvents();
    await initializePage();
    refreshHandle = setInterval(refreshMonitors, AUTO_REFRESH_MS);
});

function bindEvents() {
    document.getElementById("create_form").addEventListener("submit", handleCreateMonitor);
    document.getElementById("refresh_btn").addEventListener("click", refreshMonitors);
    document.getElementById("filter_project_select").addEventListener("change", refreshMonitors);
    document.getElementById("monitors_body").addEventListener("click", handleTableAction);
}

async function initializePage() {
    try {
        await Promise.all([loadProjects(), loadTemplates()]);
        await refreshMonitors();
    } catch (error) {
        showMessage(error.message || "Failed to load monitoring page", "error");
    }
}

async function apiGet(url) {
    const response = await fetch(url);
    const payload = await response.json();
    if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || "Request failed");
    }
    return payload;
}

async function apiSend(url, method, body) {
    const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body == null ? null : JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok || payload.ok === false) {
        throw new Error(payload.error || "Request failed");
    }
    return payload;
}

async function loadProjects() {
    const payload = await apiGet("/api/projects");
    const projectSelect = document.getElementById("project_select");
    const filterSelect = document.getElementById("filter_project_select");
    const projects = payload.projects || [];

    setSelectOptions(projectSelect, projects, "No projects available");
    setFilterOptions(filterSelect, projects);
}

async function loadTemplates() {
    const payload = await apiGet("/api/templates");
    const templateSelect = document.getElementById("template_select");
    const templates = (payload.templates || []).map((item) => item.template_name);
    setSelectOptions(templateSelect, templates, "No templates available");
}

function setSelectOptions(select, values, emptyLabel) {
    select.innerHTML = "";
    if (!values.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = emptyLabel;
        select.appendChild(option);
        return;
    }

    values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });
}

function setFilterOptions(select, values) {
    const previousValue = select.value;
    select.innerHTML = "";

    const allOption = document.createElement("option");
    allOption.value = "";
    allOption.textContent = "All Projects";
    select.appendChild(allOption);

    values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
    });

    if (values.includes(previousValue)) {
        select.value = previousValue;
    }
}

async function refreshMonitors() {
    const filterProject = document.getElementById("filter_project_select").value;
    const url = filterProject
        ? `/api/monitors?project_code=${encodeURIComponent(filterProject)}`
        : "/api/monitors";

    try {
        const payload = await apiGet(url);
        renderMonitors(payload.monitors || []);
    } catch (error) {
        showMessage(error.message || "Failed to refresh monitors", "error");
    }
}

function renderMonitors(monitors) {
    const tbody = document.getElementById("monitors_body");
    tbody.innerHTML = "";

    if (!monitors.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="empty_row">No monitors found for the current filter.</td></tr>';
        return;
    }

    monitors.forEach((monitor) => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${escapeHtml(monitor.monitor_name)}</td>
            <td>${escapeHtml(monitor.project_code)}</td>
            <td>${escapeHtml(monitor.template_name)}</td>
            <td>${renderStatusBadge(monitor.status)}</td>
            <td>${escapeHtml(String(monitor.pid || ""))}</td>
            <td>${escapeHtml(String(monitor.cpu_percent || 0))}</td>
            <td>${escapeHtml(String(monitor.memory_mb || 0))}</td>
            <td>${escapeHtml(monitor.last_started_at || "")}</td>
            <td><span class="log_text" title="${escapeHtmlAttr(monitor.last_log_message || "")}">${escapeHtml(monitor.last_log_message || "")}</span></td>
            <td>
                <div class="monitor_actions">
                    <button class="action_button primary" data-action="start" data-monitor="${escapeHtmlAttr(monitor.monitor_name)}">Start</button>
                    <button class="action_button danger" data-action="terminate" data-monitor="${escapeHtmlAttr(monitor.monitor_name)}">Terminate</button>
                    <button class="action_button secondary" data-action="delete" data-monitor="${escapeHtmlAttr(monitor.monitor_name)}">Delete</button>
                </div>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function renderStatusBadge(status) {
    const safeStatus = escapeHtml(status || "unknown");
    const className = `status_badge status_${String(status || "unknown").toLowerCase()}`;
    return `<span class="${className}">${safeStatus}</span>`;
}

async function handleCreateMonitor(event) {
    event.preventDefault();
    const project_code = document.getElementById("project_select").value;
    const template_name = document.getElementById("template_select").value;

    if (!project_code || !template_name) {
        showMessage("Select a project and template first", "error");
        return;
    }

    try {
        const payload = await apiSend("/api/monitors", "POST", { project_code, template_name });
        showMessage(`Created ${payload.data.monitor_name}`, "success");
        document.getElementById("filter_project_select").value = project_code;
        await refreshMonitors();
    } catch (error) {
        showMessage(error.message || "Failed to create monitor", "error");
    }
}

async function handleTableAction(event) {
    const button = event.target.closest("button[data-action]");
    if (!button) {
        return;
    }

    const action = button.getAttribute("data-action");
    const monitorName = button.getAttribute("data-monitor");
    if (!action || !monitorName) {
        return;
    }

    button.disabled = true;
    try {
        let payload;
        if (action === "start") {
            payload = await apiSend(`/api/monitors/${encodeURIComponent(monitorName)}/start`, "POST", {});
        } else if (action === "terminate") {
            payload = await apiSend(`/api/monitors/${encodeURIComponent(monitorName)}/terminate`, "POST", {});
        } else if (action === "delete") {
            payload = await apiSend(`/api/monitors/${encodeURIComponent(monitorName)}`, "DELETE", null);
        } else {
            return;
        }

        showMessage(`${monitorName}: ${payload.data.status}`, "success");
        await refreshMonitors();
    } catch (error) {
        showMessage(error.message || `Failed to ${action} monitor`, "error");
    } finally {
        button.disabled = false;
    }
}

function showMessage(text, kind) {
    const messageBox = document.getElementById("message_box");
    messageBox.textContent = text;
    messageBox.className = `message_box ${kind}`;
    messageBox.classList.remove("hidden");

    window.clearTimeout(showMessage.hideHandle);
    showMessage.hideHandle = window.setTimeout(() => {
        messageBox.classList.add("hidden");
    }, 3500);
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
