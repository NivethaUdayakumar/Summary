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

const APR_TRACKER_DB_LOCATION = 'AppData/App.db';
const APR_TRACKER_TABLE_NAME = 'apr-tracker';

const table = new TableBuilder({
    selector: '#aprTrackerTable',
    apiUrl: '/api/read-table',
    dbLocation: APR_TRACKER_DB_LOCATION,
    tableName: APR_TRACKER_TABLE_NAME,
    options: {
        paging: true,
        searching: true,
        ordering: {
            indicators: false,
            handler: false
        },
        orderMulti: true,
        info: true,
        pageLength: 10,
        lengthChange: true,
        order: [[0, 'asc']],
        autoWidth: false,
        responsive: false,
        stateSave: true,
        scrollX: true,
        fixedColumns: {
            left: 1
        },
        columns: [
            { data: 'item_code',  title: 'item_code',  name: 'item_code' },
            {
                data: null,
                title: 'actions',
                name: 'actions',
                orderable: false,
                searchable: false,
                className: 'dt-actions',
                render: function(data, type, row, meta) {
                    return `
                        <button class="btn-view" data-id="${row.item_code}">View</button>
                        <button class="btn-edit" data-id="${row.item_code}">Edit</button>
                        <button class="btn-delete" data-id="${row.item_code}">Delete</button>
                    `;
                }
            },
            { data: 'workstream', title: 'workstream', name: 'workstream' },
            { data: 'milestone',  title: 'milestone',  name: 'milestone' },
            { data: 'owner',      title: 'owner',      name: 'owner' },
            { data: 'status',     title: 'status',     name: 'status' },
            { data: 'due_date',   title: 'due_date',   name: 'due_date' },
            { data: 'score',      title: 'score',      name: 'score' },
        ],
        columnDefs: [
            {
                targets: '_all',
                defaultContent: ''
            },
            {
                targets: ['workstream:name', 'owner:name', 'status:name'],
                columnControl: ['order', listDropdown]
            },
            {
                targets: ['due_date:name'],
                columnControl: ['order', dateDropdown]
            },
            {
                targets: ['score:name'],
                columnControl: ['order', floatDropdown]
            }
        ]
    },
    extensions: {
        afterInit: function(dt, builder) {
            const tableEl = document.querySelector(builder.selector);

            tableEl.addEventListener('click', function(event) {
                const viewBtn = event.target.closest('.btn-view');
                const editBtn = event.target.closest('.btn-edit');
                const deleteBtn = event.target.closest('.btn-delete');

                if (viewBtn) {
                    const dt = table.getInstance();
                    const tr = event.target.closest('tr');
                    const rowData = dt.row(tr).data();

                    console.log('View row:', rowData);
                }

                if (editBtn) {
                    const id = editBtn.dataset.id;
                    console.log('Edit clicked:', id);
                }

                if (deleteBtn) {
                    const id = deleteBtn.dataset.id;
                    console.log('Delete clicked:', id);
                }
            });
        }
    }
});

table.render().catch(error => {
    console.error(error);
    alert(error.message);
});