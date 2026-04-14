let currentDbPath = '';
let currentTable = '';
let currentSchema = [];
let mainDataTable = null;
let selectedRowIndexes = new Set();
const DEFAULT_PREVIEW_ROW_LIMIT = 100;

const listDropdown = {
    extend: 'dropdown',
    content: [
        'searchList',
        'spacer',
        'orderAsc',
        'orderDesc',
        'orderClear'
    ]
};

const dateDropdown = {
    extend: 'dropdown',
    content: [
        'searchDateTime',
        'spacer',
        'orderAsc',
        'orderDesc',
        'orderClear'
    ]
};

const floatDropdown = {
    extend: 'dropdown',
    content: [
        'searchNumber',
        'spacer',
        'orderAsc',
        'orderDesc',
        'orderClear'
    ]
};

function showError(error) {
    alert(error.message || String(error));
}

async function api(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json'
        }
    };

    if (body) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(url, options);
    const data = await response.json();

    if (!response.ok || data.success === false) {
        throw new Error(data.error || 'Request failed');
    }

    return data;
}

function formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function setCurrentTableLabel(label) {
    document.getElementById('currentTableLabel').textContent = label;
}

function getPreviewRowLimit(meta) {
    const limit = Number(meta && meta.row_limit);
    return Number.isFinite(limit) && limit > 0 ? limit : DEFAULT_PREVIEW_ROW_LIMIT;
}

function formatCount(value) {
    const count = Number(value);
    return Number.isFinite(count) ? count.toLocaleString() : String(value || 0);
}

function buildPreviewLabel(label, meta) {
    if (!meta || !(Number(meta.row_limit) > 0)) {
        return label;
    }

    if (Number.isFinite(Number(meta.total_rows))) {
        return `${label} (${formatCount(meta.total_rows)} rows total, preview max ${getPreviewRowLimit(meta)})`;
    }

    return `${label} (preview max ${getPreviewRowLimit(meta)} rows)`;
}

function getTypeCategory(type) {
    const t = String(type || '').toUpperCase();

    if (t.includes('DATE') || t.includes('TIME')) return 'date';
    if (t.includes('INT')) return 'integer';
    if (t.includes('REAL') || t.includes('FLOAT') || t.includes('DOUBLE') || t.includes('NUMERIC') || t.includes('DECIMAL')) return 'number';
    return 'text';
}

function renderDbInfo(info) {
    document.getElementById('dbInfoPath').textContent = info.db_path || '';
    document.getElementById('dbInfoSize').textContent = formatBytes(info.file_size_bytes || 0);
    document.getElementById('dbInfoTableCount').textContent = String(info.table_count || 0);
}

function buildSchemaTable(columns) {
    const tbody = document.getElementById('schemaTableBody');
    tbody.innerHTML = '';

    columns.forEach(col => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${col.name || ''}</td>
            <td>${col.type || ''}</td>
            <td>${col.pk ? 'Yes' : 'No'}</td>
            <td>${col.autoincrement ? 'Yes' : 'No'}</td>
            <td>${col.notnull ? 'Yes' : 'No'}</td>
            <td>${col.default_value == null ? '' : col.default_value}</td>
        `;
        tbody.appendChild(tr);
    });
}

function updateRemoveColumnDropdown(columns) {
    const select = document.getElementById('removeColumnSelect');
    select.innerHTML = '<option value="">Select column to remove</option>';

    columns.forEach(col => {
        const option = document.createElement('option');
        option.value = col.name;
        option.textContent = col.name;
        select.appendChild(option);
    });
}

function clearRecordForm() {
    const form = document.getElementById('recordForm');
    form.querySelectorAll('[data-col]').forEach(el => {
        el.value = '';
    });
}

function buildRecordForm(columns, rowData = null) {
    const form = document.getElementById('recordForm');
    form.innerHTML = '';

    columns.forEach(col => {
        const field = document.createElement('div');
        field.className = 'record-field';

        const value = rowData && rowData[col.name] != null ? String(rowData[col.name]) : '';

        field.innerHTML = `
            <label>${col.name} (${col.type || 'TEXT'})${col.pk ? ' [PK]' : ''}</label>
            <input type="text" data-col="${col.name}" value="${value.replace(/"/g, '&quot;')}" />
        `;

        form.appendChild(field);
    });
}

function getRecordFormPayload() {
    const payload = {};
    document.querySelectorAll('#recordForm [data-col]').forEach(el => {
        payload[el.dataset.col] = el.value === '' ? null : el.value;
    });
    return payload;
}

async function openDb() {
    const dbPath = document.getElementById('dbPath').value.trim();
    if (!dbPath) {
        alert('Please enter DB path');
        return;
    }

    const data = await api('/api/database/open', 'POST', {
        db_path: dbPath
    });

    currentDbPath = dbPath;
    renderDbInfo(data.info);

    currentTable = '';
    currentSchema = [];
    setCurrentTableLabel('None');
    buildSchemaTable([]);
    buildRecordForm([]);
    updateRemoveColumnDropdown([]);
    renderMainTable([], []);

    await Promise.all([loadTables(), listTemplates()]);

    alert('Database loaded');
}

async function refreshDbInfo() {
    if (!currentDbPath) return;

    const data = await api(`/api/database/info?db_path=${encodeURIComponent(currentDbPath)}`);
    renderDbInfo(data.info);
}

async function loadTables() {
    if (!currentDbPath) return;

    const wrap = document.getElementById('tableList');
    wrap.innerHTML = '<div class="table-meta">Loading tables...</div>';

    const data = await api(`/api/database/tables?db_path=${encodeURIComponent(currentDbPath)}`);
    wrap.innerHTML = '';
    const previewRowLimit = Number(data.preview_row_limit) > 0
        ? Number(data.preview_row_limit)
        : DEFAULT_PREVIEW_ROW_LIMIT;

    if (!data.tables || data.tables.length === 0) {
        wrap.innerHTML = '<div class="table-meta">No tables yet</div>';
        return;
    }

    (data.tables || []).forEach(table => {
        const row = document.createElement('div');
        row.className = 'table-item';

        row.innerHTML = `
            <div>
                <div class="table-name">${table.name}</div>
                <div class="table-meta">Exact row count shown on open, preview up to ${previewRowLimit} rows</div>
            </div>
            <button class="ui button small" data-table="${table.name}">Open</button>
        `;

        row.querySelector('button').addEventListener('click', () => {
            loadTable(table.name).catch(showError);
        });

        wrap.appendChild(row);
    });
}

async function loadTable(tableName) {
    currentTable = tableName;
    setCurrentTableLabel(`${tableName} (loading preview...)`);

    const [schemaData, data] = await Promise.all([
        api(`/api/database/table_schema?db_path=${encodeURIComponent(currentDbPath)}&table_name=${encodeURIComponent(tableName)}`),
        api(`/api/database/table_data?db_path=${encodeURIComponent(currentDbPath)}&table_name=${encodeURIComponent(tableName)}`)
    ]);

    currentSchema = schemaData.schema.columns || [];

    buildSchemaTable(currentSchema);
    updateRemoveColumnDropdown(currentSchema);
    buildRecordForm(currentSchema);

    renderMainTable(data.rows || [], currentSchema);
    setCurrentTableLabel(buildPreviewLabel(tableName, data));

    selectedRowIndexes.clear();
}

function buildColumnsFromSchema(schema, rows) {
    if (schema && schema.length > 0) {
        return schema.map(col => ({
            data: col.name,
            title: col.name,
            name: col.name
        }));
    }

    if (rows.length > 0) {
        return Object.keys(rows[0]).map(key => ({
            data: key,
            title: key,
            name: key
        }));
    }

    return [];
}

function buildColumnDefs(schema) {
    const defs = [
        {
            targets: '_all',
            defaultContent: ''
        }
    ];

    schema.forEach(col => {
        const category = getTypeCategory(col.type);

        if (category === 'date') {
            defs.push({
                targets: `${col.name}:name`,
                columnControl: ['order', dateDropdown]
            });
        } else if (category === 'integer' || category === 'number') {
            defs.push({
                targets: `${col.name}:name`,
                columnControl: ['order', floatDropdown]
            });
        } else {
            defs.push({
                targets: `${col.name}:name`,
                columnControl: ['order', listDropdown]
            });
        }
    });

    return defs;
}

function bindSelectionEvents() {
    const tableEl = document.getElementById('mainDataTable');

    $(tableEl).off('click', 'tbody tr');
    $(tableEl).on('click', 'tbody tr', function(event) {
        if (!mainDataTable) return;

        const row = mainDataTable.row(this);
        if (!row || !row.data()) return;

        const rowIndex = row.index();
        const rowData = row.data();

        if (selectedRowIndexes.has(rowIndex)) {
            selectedRowIndexes.delete(rowIndex);
            $(this).removeClass('selected-row');
        } else {
            selectedRowIndexes.add(rowIndex);
            $(this).addClass('selected-row');
        }

        if (selectedRowIndexes.size === 1) {
            const index = Array.from(selectedRowIndexes)[0];
            const data = mainDataTable.row(index).data();
            buildRecordForm(currentSchema, data);
        } else if (selectedRowIndexes.size === 0) {
            buildRecordForm(currentSchema);
        } else {
            clearRecordForm();
        }
    });
}

function renderMainTable(rows, schema) {
    const tableEl = document.getElementById('mainDataTable');

    if ($.fn.DataTable.isDataTable(tableEl)) {
        $(tableEl).DataTable().destroy();
        tableEl.innerHTML = '';
    }

    selectedRowIndexes.clear();

    const columns = buildColumnsFromSchema(schema, rows);
    const columnDefs = buildColumnDefs(schema);

    mainDataTable = $(tableEl).DataTable({
        data: rows,
        paging: true,
        searching: true,
        deferRender: true,
        ordering: {
            indicators: false,
            handler: false
        },
        orderMulti: true,
        info: true,
        pageLength: 10,
        lengthChange: true,
        order: columns.length > 0 ? [[0, 'asc']] : [],
        autoWidth: true,
        responsive: false,
        stateSave: true,
        scrollX: true,
        columns: columns,
        columnDefs: columnDefs
    });

    bindSelectionEvents();
}

function getWhereFromRow(rowData) {
    const pkCols = currentSchema.filter(col => col.pk);
    if (pkCols.length === 0) return null;

    const where = {};
    pkCols.forEach(col => {
        where[col.name] = rowData[col.name];
    });
    return where;
}

async function createTable() {
    if (!currentDbPath) {
        alert('Open DB first');
        return;
    }

    const tableName = document.getElementById('newTableName').value.trim();
    if (!tableName) {
        alert('Enter table name');
        return;
    }

    await api('/api/database/create_table', 'POST', {
        db_path: currentDbPath,
        table_name: tableName
    });

    await refreshDbInfo();
    await loadTables();
    alert('Table created');
}

async function deleteTable() {
    if (!currentDbPath || !currentTable) {
        alert('Open a table first');
        return;
    }

    await api('/api/database/delete_table', 'POST', {
        db_path: currentDbPath,
        table_name: currentTable
    });

    await refreshDbInfo();
    await loadTables();

    currentTable = '';
    currentSchema = [];
    setCurrentTableLabel('None');
    buildSchemaTable([]);
    buildRecordForm([]);
    updateRemoveColumnDropdown([]);
    renderMainTable([], []);

    alert('Table deleted');
}

async function addColumn() {
    if (!currentDbPath || !currentTable) {
        alert('Open a table first');
        return;
    }

    const payload = {
        db_path: currentDbPath,
        table_name: currentTable,
        column_name: document.getElementById('newColumnName').value.trim(),
        column_type: document.getElementById('newColumnType').value,
        not_null: document.getElementById('newColumnNotNull').checked,
        primary_key: document.getElementById('newColumnPk').checked,
        autoincrement: document.getElementById('newColumnAuto').checked,
        default_value: document.getElementById('newColumnDefault').value.trim()
    };

    if (!payload.column_name) {
        alert('Enter column name');
        return;
    }

    await api('/api/database/add_column', 'POST', payload);

    await loadTable(currentTable);
    alert('Column added');
}

async function removeColumn() {
    if (!currentDbPath || !currentTable) {
        alert('Open a table first');
        return;
    }

    const columnName = document.getElementById('removeColumnSelect').value;
    if (!columnName) {
        alert('Select column to remove');
        return;
    }

    await api('/api/database/remove_column', 'POST', {
        db_path: currentDbPath,
        table_name: currentTable,
        column_name: columnName
    });

    await loadTable(currentTable);
    alert('Column removed');
}

async function insertRecord() {
    if (!currentDbPath || !currentTable) {
        alert('Open a table first');
        return;
    }

    const record = getRecordFormPayload();

    await api('/api/database/insert_record', 'POST', {
        db_path: currentDbPath,
        table_name: currentTable,
        record: record
    });

    await loadTable(currentTable);
    alert('Record created');
}

async function updateSelectedRow() {
    if (!currentDbPath || !currentTable) {
        alert('Open a table first');
        return;
    }

    if (!mainDataTable || selectedRowIndexes.size !== 1) {
        alert('Select exactly one row to update');
        return;
    }

    const index = Array.from(selectedRowIndexes)[0];
    const originalRow = mainDataTable.row(index).data();
    const where = getWhereFromRow(originalRow);

    if (!where) {
        alert('Primary key required for update');
        return;
    }

    const setValues = getRecordFormPayload();

    await api('/api/database/update_record', 'POST', {
        db_path: currentDbPath,
        table_name: currentTable,
        set_values: setValues,
        where: where
    });

    await loadTable(currentTable);
    alert('Row updated');
}

async function deleteSelectedRows() {
    if (!currentDbPath || !currentTable) {
        alert('Open a table first');
        return;
    }

    if (!mainDataTable || selectedRowIndexes.size === 0) {
        alert('Select one or more rows to delete');
        return;
    }

    const rowsToDelete = Array.from(selectedRowIndexes).map(index => mainDataTable.row(index).data());

    for (const row of rowsToDelete) {
        const where = getWhereFromRow(row);
        if (!where) {
            alert('Primary key required for delete');
            return;
        }

        await api('/api/database/delete_record', 'POST', {
            db_path: currentDbPath,
            table_name: currentTable,
            where: where
        });
    }

    await loadTable(currentTable);
    alert('Selected rows deleted');
}

async function runQuery() {
    if (!currentDbPath) {
        alert('Open DB first');
        return;
    }

    const sql = document.getElementById('queryText').value.trim();
    if (!sql) {
        alert('Enter SQL query');
        return;
    }

    setCurrentTableLabel('Query Result (running...)');
    const data = await api('/api/database/query', 'POST', {
        db_path: currentDbPath,
        sql: sql
    });

    const rows = data.rows || [];
    const querySchema = rows.length > 0
        ? Object.keys(rows[0]).map(key => ({
            name: key,
            type: 'TEXT',
            pk: 0,
            autoincrement: 0,
            notnull: 0,
            default_value: null
        }))
        : [];

    setCurrentTableLabel(buildPreviewLabel('Query Result', data));
    buildSchemaTable(querySchema);
    buildRecordForm([]);
    updateRemoveColumnDropdown([]);
    renderMainTable(rows, querySchema);

    alert(data.message || 'Query executed');
}

async function saveTemplate() {
    if (!currentDbPath) {
        alert('Open DB first');
        return;
    }

    const templateName = document.getElementById('templateName').value.trim();
    if (!templateName) {
        alert('Enter template name');
        return;
    }

    await api('/api/database/save_template', 'POST', {
        db_path: currentDbPath,
        template_name: templateName
    });

    await listTemplates();
    alert('Template saved');
}

async function listTemplates() {
    const data = await api('/api/database/list_templates');
    const select = document.getElementById('templateList');
    select.innerHTML = '';

    (data.templates || []).forEach(name => {
        const option = document.createElement('option');
        option.value = name;
        option.textContent = name;
        select.appendChild(option);
    });
}

async function createDbFromTemplate() {
    const templateName = document.getElementById('templateList').value;
    const newDbPath = document.getElementById('newDbFromTemplatePath').value.trim();

    if (!templateName || !newDbPath) {
        alert('Select template and enter new DB path');
        return;
    }

    await api('/api/database/create_from_template', 'POST', {
        template_name: templateName,
        new_db_path: newDbPath
    });

    document.getElementById('dbPath').value = newDbPath;
    await openDb();
    alert('DB created from template');
}

function clearAllFilters() {
    if (!mainDataTable) return;

    mainDataTable.search('');
    mainDataTable.columns().search('');
    mainDataTable.order([]);

    const tableContainer = document.querySelector('#mainDataTable');
    if (tableContainer) {
        const selects = tableContainer.parentElement.querySelectorAll('thead select');
        selects.forEach(select => {
            if (select.options.length > 0) {
                select.selectedIndex = 0;
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });

        const inputs = tableContainer.parentElement.querySelectorAll('thead input');
        inputs.forEach(input => {
            input.value = '';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
        });
    }

    mainDataTable.draw();
}

function bindEvents() {
    document.getElementById('openDbBtn').addEventListener('click', () => openDb().catch(showError));
    document.getElementById('createTableBtn').addEventListener('click', () => createTable().catch(showError));
    document.getElementById('deleteTableBtn').addEventListener('click', () => deleteTable().catch(showError));
    document.getElementById('addColumnBtn').addEventListener('click', () => addColumn().catch(showError));
    document.getElementById('removeColumnBtn').addEventListener('click', () => removeColumn().catch(showError));
    document.getElementById('insertRecordBtn').addEventListener('click', () => insertRecord().catch(showError));
    document.getElementById('updateSelectedRowBtn').addEventListener('click', () => updateSelectedRow().catch(showError));
    document.getElementById('deleteSelectedRowsBtn').addEventListener('click', () => deleteSelectedRows().catch(showError));
    document.getElementById('clearRecordFormBtn').addEventListener('click', clearRecordForm);
    document.getElementById('runQueryBtn').addEventListener('click', () => runQuery().catch(showError));
    document.getElementById('reloadCurrentTableBtn').addEventListener('click', () => {
        if (!currentTable) {
            alert('No current table');
            return;
        }
        loadTable(currentTable).catch(showError);
    });
    document.getElementById('saveTemplateBtn').addEventListener('click', () => saveTemplate().catch(showError));
    document.getElementById('listTemplatesBtn').addEventListener('click', () => listTemplates().catch(showError));
    document.getElementById('createDbFromTemplateBtn').addEventListener('click', () => createDbFromTemplate().catch(showError));
    document.getElementById('clearFiltersBtn').addEventListener('click', clearAllFilters);
}

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    buildSchemaTable([]);
    buildRecordForm([]);
    updateRemoveColumnDropdown([]);
    renderMainTable([], []);
    listTemplates().catch(() => {});
});
