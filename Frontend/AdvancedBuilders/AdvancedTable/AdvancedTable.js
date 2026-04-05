class TableBuilder {
    constructor(config = {}) {
        this.selector = config.selector;
        this.apiUrl = config.apiUrl || '/api/read-table';
        this.dbLocation = config.dbLocation;
        this.tableName = config.tableName;

        this.fetchOptions = config.fetchOptions || {};
        this.columns = config.columns || null;
        this.transformResponse = config.transformResponse || null;

        this.options = config.options || {};
        this.extensions = config.extensions || {};

        this.instance = null;
    }

    validateConfig() {
        if (!this.selector) {
            throw new Error('selector is required');
        }

        if (typeof DataTable === 'undefined') {
            throw new Error('DataTable is not loaded. Check DataTables JS file and load order.');
        }
    }

    getTableElement() {
        const table = document.querySelector(this.selector);
        if (!table) {
            throw new Error(`Table element not found: ${this.selector}`);
        }
        return table;
    }

    clearTableElement() {
        const table = this.getTableElement();
        table.innerHTML = '';
    }

    destroy() {
        if (this.instance) {
            this.instance.destroy();
            this.instance = null;
        }
        this.clearTableElement();
    }

    async fetchTableData() {
        if (!this.dbLocation || !this.tableName) {
            return null;
        }

        const response = await fetch(this.apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(this.fetchOptions.headers || {})
            },
            ...this.fetchOptions,
            body: JSON.stringify({
                db_location: this.dbLocation,
                table_name: this.tableName,
                ...(this.fetchOptions.body || {})
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Failed to load table data');
        }

        return result;
    }

    buildColumnsFromApi(apiColumns) {
        return apiColumns.map(col => ({
            title: col.name,
            data: col.name,
            defaultContent: ''
        }));
    }

    buildHeader(columns) {
        const table = this.getTableElement();
        const thead = document.createElement('thead');
        const row = document.createElement('tr');

        columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col.title || col.data || '';
            row.appendChild(th);
        });

        thead.appendChild(row);
        table.appendChild(thead);
    }

    buildFooter(columns) {
        const table = this.getTableElement();
        const tfoot = document.createElement('tfoot');
        const row = document.createElement('tr');

        columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col.title || '';
            row.appendChild(th);
        });

        tfoot.appendChild(row);
        table.appendChild(tfoot);
    }

    addColumnTextFilters(columns, where = 'header') {
        const table = this.getTableElement();
        const section = where === 'footer'
            ? table.querySelector('tfoot')
            : table.querySelector('thead');

        if (!section) return;

        const filterRow = document.createElement('tr');

        columns.forEach((col, index) => {
            const th = document.createElement('th');
            const input = document.createElement('input');

            input.type = 'text';
            input.placeholder = `Filter ${col.title || col.data || ''}`;
            input.dataset.columnIndex = index;
            input.style.width = '100%';
            input.style.boxSizing = 'border-box';

            th.appendChild(input);
            filterRow.appendChild(th);
        });

        section.appendChild(filterRow);
    }

    bindColumnTextFilters(where = 'header') {
        const table = this.getTableElement();
        const root = where === 'footer'
            ? table.querySelector('tfoot')
            : table.querySelector('thead');

        if (!root || !this.instance) return;

        root.querySelectorAll('input[data-column-index]').forEach(input => {
            const colIndex = Number(input.dataset.columnIndex);

            const handler = () => {
                this.instance.column(colIndex).search(input.value).draw();
            };

            input.addEventListener('keyup', handler);
            input.addEventListener('change', handler);
        });
    }

    applyExtensionSetup(columns) {
        if (!this.extensions) return;

        if (this.extensions.columnTextFilters?.enabled) {
            const where = this.extensions.columnTextFilters.position || 'header';
            this.addColumnTextFilters(columns, where);
        }
    }

    applyExtensionBindings() {
        if (!this.extensions || !this.instance) return;

        if (this.extensions.columnTextFilters?.enabled) {
            const where = this.extensions.columnTextFilters.position || 'header';
            this.bindColumnTextFilters(where);
        }

        if (typeof this.extensions.afterInit === 'function') {
            this.extensions.afterInit(this.instance, this);
        }
    }

    async resolveData() {
        let result = null;

        if (typeof this.transformResponse === 'function') {
            result = await this.transformResponse();
        } else {
            result = await this.fetchTableData();
        }

        if (!result) {
            throw new Error('No data returned');
        }

        const columns = this.columns || this.buildColumnsFromApi(result.columns || []);
        const data = result.rows || result.data || [];

        return { columns, data, raw: result };
    }

    async render() {
        this.validateConfig();

        const { columns, data, raw } = await this.resolveData();

        this.destroy();
        this.buildHeader(columns);

        if (this.extensions.columnTextFilters?.enabled &&
            this.extensions.columnTextFilters.position === 'footer') {
            this.buildFooter(columns);
        }

        this.applyExtensionSetup(columns);

        const dtOptions = {
            data,
            columns,
            ...this.options
        };

        this.instance = new DataTable(this.selector, dtOptions);

        this.applyExtensionBindings();

        if (typeof this.options.initCompleteUser === 'function') {
            this.options.initCompleteUser(this.instance, raw, this);
        }

        return this.instance;
    }

    async reload(dbLocation = null, tableName = null) {
        if (dbLocation) this.dbLocation = dbLocation;
        if (tableName) this.tableName = tableName;
        return await this.render();
    }

    getInstance() {
        return this.instance;
    }
}