window.APR_BUTTONS = window.APR_BUTTONS || [];

(function () {
    var DB_LOCATION = 'AppData/App.db';
    var WATCHLIST_TABLE = 'apr_watchlist';
    var WEEKLY_TABLE = 'apr_weekly';
    var DEFAULT_WATCHLIST = 'APR Weekly';
    var WATCHLIST_RECORD = 'watchlist';
    var RUN_RECORD = 'run';
    var CURRENT_WEEK_LIMIT = 3;
    var RUN_ID_FIELDS = ['Job', 'Milestone', 'Block', 'Stage'];
    var TRACKER_FIELDS = ['Job', 'Milestone', 'Block', 'Stage', 'Dft_release', 'User', 'Status', 'Comments', 'Promote'];

    var popupWindow = null;
    var popupState = {
        activeRow: null,
        userId: '',
        views: [],
        selectedViewKey: 'current',
        currentWeekInfo: null,
        isLoading: false,
        statusMessage: '',
        statusIsError: false
    };

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function safeJsonParse(value, fallback) {
        if (!value) {
            return fallback;
        }

        try {
            return JSON.parse(value);
        } catch (error) {
            return fallback;
        }
    }

    function nowIso() {
        return new Date().toISOString();
    }

    function padNumber(value) {
        return String(value).padStart(2, '0');
    }

    function getWeekInfo(dateInput) {
        var date = dateInput ? new Date(dateInput) : new Date();
        if (Number.isNaN(date.getTime())) {
            date = new Date();
        }

        date.setHours(0, 0, 0, 0);

        var isoDate = new Date(date);
        isoDate.setDate(isoDate.getDate() + 3 - ((isoDate.getDay() + 6) % 7));

        var isoYear = isoDate.getFullYear();
        var weekOne = new Date(isoYear, 0, 4);
        weekOne.setHours(0, 0, 0, 0);
        weekOne.setDate(weekOne.getDate() + 3 - ((weekOne.getDay() + 6) % 7));

        var isoWeek = 1 + Math.round((isoDate - weekOne) / 604800000);

        var weekStart = new Date(date);
        weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7));
        weekStart.setHours(0, 0, 0, 0);

        var weekEnd = new Date(weekStart);
        weekEnd.setDate(weekEnd.getDate() + 6);
        weekEnd.setHours(23, 59, 59, 999);

        return {
            key: isoYear + '-W' + padNumber(isoWeek),
            label: 'Week of ' + weekStart.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric'
            }),
            start: weekStart.toISOString(),
            end: weekEnd.toISOString()
        };
    }

    function metadataPayloadForWeek(weekInfo) {
        return JSON.stringify({
            week_key: weekInfo.key,
            week_label: weekInfo.label,
            week_start: weekInfo.start,
            week_end: weekInfo.end
        });
    }

    function getWeekInfoFromMetadataRow(row) {
        if (!row) {
            return null;
        }

        var payload = safeJsonParse(row.run_payload, {});
        if (payload.week_key) {
            return {
                key: String(payload.week_key),
                label: String(payload.week_label || ('Week ' + payload.week_key)),
                start: String(payload.week_start || ''),
                end: String(payload.week_end || '')
            };
        }

        return getWeekInfo(row.updated_at || row.created_at || new Date());
    }

    function getRowLabel(row) {
        if (typeof window.getAPRTrackerRowLabel === 'function') {
            return window.getAPRTrackerRowLabel(row || {});
        }

        return [row.Job, row.Milestone, row.Block, row.Stage]
            .filter(function (value) {
                return value;
            })
            .join(' / ');
    }

    function buildPopupShell(doc) {
        doc.open();
        doc.write(
            '<!DOCTYPE html>' +
            '<html lang="en">' +
            '<head>' +
            '<meta charset="utf-8">' +
            '<meta name="viewport" content="width=device-width, initial-scale=1">' +
            '<title>APR Watchlist</title>' +
            '<style>' +
            ':root { color-scheme: light; }' +
            '* { box-sizing: border-box; }' +
            'body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #f6f8fb; color: #14213d; }' +
            '.apr-watchlist-shell { padding: 18px; }' +
            '.apr-watchlist-card { background: #ffffff; border: 1px solid #d7deea; border-radius: 12px; box-shadow: 0 10px 28px rgba(20, 33, 61, 0.08); padding: 16px; }' +
            '.apr-watchlist-header { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 16px; }' +
            '.apr-watchlist-title { margin: 0; font-size: 22px; font-weight: 700; }' +
            '.apr-watchlist-subtitle { margin: 4px 0 0; color: #50627d; font-size: 13px; }' +
            '.apr-watchlist-toolbar { display: flex; flex-wrap: wrap; gap: 8px; }' +
            '.apr-watchlist-button { border: 0; border-radius: 8px; padding: 9px 14px; font-size: 13px; font-weight: 600; cursor: pointer; background: #0f6cbd; color: #ffffff; }' +
            '.apr-watchlist-button.secondary { background: #e8eef7; color: #14213d; }' +
            '.apr-watchlist-button.danger { background: #c0392b; }' +
            '.apr-watchlist-button:disabled { opacity: 0.55; cursor: not-allowed; }' +
            '.apr-watchlist-grid { display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr); gap: 16px; }' +
            '.apr-watchlist-stack { display: grid; gap: 16px; }' +
            '.apr-watchlist-panel-title { margin: 0 0 12px; font-size: 15px; font-weight: 700; }' +
            '.apr-watchlist-run { display: grid; gap: 8px; font-size: 13px; }' +
            '.apr-watchlist-run strong { display: block; font-size: 16px; }' +
            '.apr-watchlist-meta { display: grid; gap: 6px; color: #415168; }' +
            '.apr-watchlist-meta span { display: block; }' +
            '.apr-watchlist-controls { display: grid; gap: 10px; }' +
            '.apr-watchlist-select { width: 100%; min-height: 38px; border: 1px solid #c4cfdf; border-radius: 8px; padding: 8px 10px; font-size: 14px; background: #ffffff; color: #14213d; }' +
            '.apr-watchlist-note { margin: 0; color: #5d6f88; font-size: 12px; line-height: 1.5; }' +
            '.apr-watchlist-status { min-height: 20px; margin-bottom: 12px; font-size: 13px; color: #315f2b; }' +
            '.apr-watchlist-status.error { color: #b42318; }' +
            '.apr-watchlist-table-wrap { overflow: auto; border: 1px solid #d7deea; border-radius: 10px; background: #fbfcfe; }' +
            '.apr-watchlist-table { width: 100%; border-collapse: collapse; font-size: 13px; }' +
            '.apr-watchlist-table th, .apr-watchlist-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; vertical-align: top; }' +
            '.apr-watchlist-table th { background: #eef3f9; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: #5d6f88; position: sticky; top: 0; }' +
            '.apr-watchlist-table tr:last-child td { border-bottom: 0; }' +
            '.apr-watchlist-empty { padding: 26px 18px; text-align: center; color: #5d6f88; font-size: 13px; }' +
            '.apr-watchlist-pill-row { display: flex; flex-wrap: wrap; gap: 8px; }' +
            '.apr-watchlist-pill { display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 9px; font-size: 11px; font-weight: 700; background: #e8eef7; color: #31445f; }' +
            '.apr-watchlist-pill.current { background: #d8f0dc; color: #215732; }' +
            '.apr-watchlist-pill.archive { background: #f3e8cf; color: #78591c; }' +
            '@media (max-width: 860px) { .apr-watchlist-grid { grid-template-columns: 1fr; } .apr-watchlist-shell { padding: 12px; } }' +
            '</style>' +
            '</head>' +
            '<body>' +
            '<div id="apr-watchlist-root" class="apr-watchlist-shell"></div>' +
            '</body>' +
            '</html>'
        );
        doc.close();
    }

    function ensurePopupWindow() {
        if (popupWindow && !popupWindow.closed) {
            if (!popupWindow.document.getElementById('apr-watchlist-root')) {
                buildPopupShell(popupWindow.document);
            }
            return popupWindow;
        }

        popupWindow = window.open(
            '',
            'apr-watchlist',
            'popup=yes,width=1120,height=760,resizable=yes,scrollbars=yes'
        );

        if (!popupWindow) {
            alert('Unable to open the watchlist window. Please allow pop-ups for this site.');
            return null;
        }

        buildPopupShell(popupWindow.document);
        return popupWindow;
    }

    function parseResponsePayload(response, text) {
        if (!text) {
            return {};
        }

        try {
            return JSON.parse(text);
        } catch (error) {
            return {
                success: response.ok,
                raw_text: text
            };
        }
    }

    function requestJson(url, method, body) {
        var options = {
            method: method,
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json'
            }
        };

        if (body !== undefined) {
            options.headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(body);
        }

        return fetch(url, options).then(function (response) {
            return response.text().then(function (text) {
                var payload = parseResponsePayload(response, text);

                if (!response.ok || payload.success === false) {
                    var message = payload.error || payload.message || payload.raw_text || ('Request failed (' + response.status + ')');
                    throw new Error(message);
                }

                return payload;
            });
        });
    }

    function requestTableApi(path, body) {
        return requestJson(path, 'POST', body);
    }

    function runSeries(tasks) {
        return tasks.reduce(function (promise, task) {
            return promise.then(task);
        }, Promise.resolve());
    }

    function findView(viewKey) {
        for (var i = 0; i < popupState.views.length; i += 1) {
            if (popupState.views[i].key === viewKey) {
                return popupState.views[i];
            }
        }

        return null;
    }

    function syncSelectedView() {
        if (!popupState.views.length) {
            popupState.selectedViewKey = 'current';
            return;
        }

        if (findView(popupState.selectedViewKey)) {
            return;
        }

        popupState.selectedViewKey = popupState.views[0].key;
    }

    function setStatus(message, isError) {
        popupState.statusMessage = message || '';
        popupState.statusIsError = Boolean(isError);
        renderPopup();
    }

    function normalizeRun(run) {
        if (!run || typeof run !== 'object') {
            throw new Error('Select a tracker row first.');
        }

        var normalized = {};

        TRACKER_FIELDS.forEach(function (fieldName) {
            var value = run[fieldName];
            normalized[fieldName] = value == null ? '' : String(value).trim();
        });

        var missingFields = RUN_ID_FIELDS.filter(function (fieldName) {
            return !normalized[fieldName];
        });

        if (missingFields.length) {
            throw new Error('Run must include Job, Milestone, Block, and Stage.');
        }

        normalized.run_key = RUN_ID_FIELDS.map(function (fieldName) {
            return normalized[fieldName];
        }).join('||');

        return normalized;
    }

    function ensurePopupStateUser() {
        if (popupState.userId) {
            return Promise.resolve(popupState.userId);
        }

        return requestJson('/api/session', 'GET').then(function (payload) {
            var userId = String(payload.user_id || '').trim().toLowerCase();
            if (!userId) {
                throw new Error('user_id missing from session');
            }

            popupState.userId = userId;
            return userId;
        });
    }

    function ensureWatchlistTable() {
        return requestTableApi('/api/create-table', {
            db_location: DB_LOCATION,
            table_name: WATCHLIST_TABLE,
            columns: {
                id: 'INTEGER PRIMARY KEY AUTOINCREMENT',
                record_type: 'TEXT NOT NULL',
                user_id: 'TEXT NOT NULL',
                watchlist_name: 'TEXT NOT NULL',
                is_default: 'INTEGER NOT NULL DEFAULT 0',
                run_key: 'TEXT NOT NULL DEFAULT \'\'',
                job: 'TEXT',
                milestone: 'TEXT',
                block: 'TEXT',
                stage: 'TEXT',
                tracker_user: 'TEXT',
                dft_release: 'TEXT',
                run_status: 'TEXT',
                comments: 'TEXT',
                promote: 'TEXT',
                run_payload: 'TEXT NOT NULL DEFAULT \'{}\'',
                created_at: 'TEXT NOT NULL',
                updated_at: 'TEXT NOT NULL'
            }
        });
    }

    function ensureWeeklyArchiveTable() {
        return requestTableApi('/api/create-table', {
            db_location: DB_LOCATION,
            table_name: WEEKLY_TABLE,
            columns: {
                id: 'INTEGER PRIMARY KEY AUTOINCREMENT',
                user_id: 'TEXT NOT NULL',
                week_key: 'TEXT NOT NULL',
                week_label: 'TEXT NOT NULL',
                week_start: 'TEXT NOT NULL',
                week_end: 'TEXT NOT NULL',
                source_watchlist: 'TEXT NOT NULL',
                run_key: 'TEXT NOT NULL',
                job: 'TEXT',
                milestone: 'TEXT',
                block: 'TEXT',
                stage: 'TEXT',
                tracker_user: 'TEXT',
                dft_release: 'TEXT',
                run_status: 'TEXT',
                comments: 'TEXT',
                promote: 'TEXT',
                run_payload: 'TEXT NOT NULL DEFAULT \'{}\'',
                archived_at: 'TEXT NOT NULL'
            }
        });
    }

    function fetchCurrentMetadataRow(userId) {
        return requestTableApi('/api/query-table', {
            db_location: DB_LOCATION,
            query: 'SELECT * FROM "apr_watchlist" WHERE "user_id" = ? AND "record_type" = ? AND lower("watchlist_name") = lower(?) ORDER BY "id" ASC LIMIT 1',
            params: [userId, WATCHLIST_RECORD, DEFAULT_WATCHLIST]
        }).then(function (payload) {
            return payload.rows && payload.rows.length ? payload.rows[0] : null;
        });
    }

    function fetchCurrentRunRows(userId) {
        return requestTableApi('/api/query-table', {
            db_location: DB_LOCATION,
            query: 'SELECT * FROM "apr_watchlist" WHERE "user_id" = ? AND "record_type" = ? AND lower("watchlist_name") = lower(?) ORDER BY lower("block") ASC, lower("job") ASC, lower("stage") ASC',
            params: [userId, RUN_RECORD, DEFAULT_WATCHLIST]
        }).then(function (payload) {
            return Array.isArray(payload.rows) ? payload.rows : [];
        });
    }

    function fetchArchivedRows(userId) {
        return requestTableApi('/api/query-table', {
            db_location: DB_LOCATION,
            query: 'SELECT * FROM "apr_weekly" WHERE "user_id" = ? AND lower("source_watchlist") = lower(?) ORDER BY "week_start" DESC, lower("block") ASC, lower("job") ASC, lower("stage") ASC',
            params: [userId, DEFAULT_WATCHLIST]
        }).then(function (payload) {
            return Array.isArray(payload.rows) ? payload.rows : [];
        });
    }

    function insertCurrentMetadataRow(userId, weekInfo) {
        var timestamp = nowIso();

        return requestTableApi('/api/insert-record', {
            db_location: DB_LOCATION,
            table_name: WATCHLIST_TABLE,
            record: {
                record_type: WATCHLIST_RECORD,
                user_id: userId,
                watchlist_name: DEFAULT_WATCHLIST,
                is_default: 1,
                run_key: '',
                run_payload: metadataPayloadForWeek(weekInfo),
                created_at: timestamp,
                updated_at: timestamp
            }
        }).then(function () {
            return fetchCurrentMetadataRow(userId);
        });
    }

    function updateCurrentMetadataRow(userId, metadataId, weekInfo) {
        return requestTableApi('/api/update-record', {
            db_location: DB_LOCATION,
            table_name: WATCHLIST_TABLE,
            updates: {
                watchlist_name: DEFAULT_WATCHLIST,
                is_default: 1,
                run_payload: metadataPayloadForWeek(weekInfo),
                updated_at: nowIso()
            },
            criteria: {
                id: metadataId,
                user_id: userId,
                record_type: WATCHLIST_RECORD
            }
        });
    }

    function ensureCurrentWeekMetadata(userId, currentWeekInfo) {
        return fetchCurrentMetadataRow(userId).then(function (metadataRow) {
            if (metadataRow) {
                return metadataRow;
            }

            return insertCurrentMetadataRow(userId, currentWeekInfo);
        });
    }

    function archivePreviousWeek(userId, previousWeekInfo, runRows) {
        if (!previousWeekInfo || !previousWeekInfo.key || !runRows.length) {
            return Promise.resolve();
        }

        return requestTableApi('/api/query-table', {
            db_location: DB_LOCATION,
            query: 'DELETE FROM "apr_weekly" WHERE "user_id" = ? AND "week_key" = ? AND lower("source_watchlist") = lower(?)',
            params: [userId, previousWeekInfo.key, DEFAULT_WATCHLIST]
        }).then(function () {
            var archivedAt = nowIso();

            return runSeries(runRows.map(function (row) {
                return function () {
                    return requestTableApi('/api/insert-record', {
                        db_location: DB_LOCATION,
                        table_name: WEEKLY_TABLE,
                        record: {
                            user_id: userId,
                            week_key: previousWeekInfo.key,
                            week_label: previousWeekInfo.label,
                            week_start: previousWeekInfo.start || '',
                            week_end: previousWeekInfo.end || '',
                            source_watchlist: DEFAULT_WATCHLIST,
                            run_key: row.run_key || '',
                            job: row.job || '',
                            milestone: row.milestone || '',
                            block: row.block || '',
                            stage: row.stage || '',
                            tracker_user: row.tracker_user || '',
                            dft_release: row.dft_release || '',
                            run_status: row.run_status || '',
                            comments: row.comments || '',
                            promote: row.promote || '',
                            run_payload: row.run_payload || '{}',
                            archived_at: archivedAt
                        }
                    });
                };
            }));
        });
    }

    function clearCurrentWeekRuns(userId) {
        return requestTableApi('/api/query-table', {
            db_location: DB_LOCATION,
            query: 'DELETE FROM "apr_watchlist" WHERE "user_id" = ? AND "record_type" = ? AND lower("watchlist_name") = lower(?)',
            params: [userId, RUN_RECORD, DEFAULT_WATCHLIST]
        });
    }

    function rolloverWeekIfNeeded(userId, metadataRow, currentRunRows, currentWeekInfo) {
        var storedWeekInfo = getWeekInfoFromMetadataRow(metadataRow);
        var hasWeekChanged = storedWeekInfo && storedWeekInfo.key !== currentWeekInfo.key;
        var metadataNeedsRefresh = !storedWeekInfo || storedWeekInfo.key !== currentWeekInfo.key || storedWeekInfo.label !== currentWeekInfo.label;

        if (!metadataRow) {
            return Promise.resolve();
        }

        if (!hasWeekChanged && !metadataNeedsRefresh) {
            return Promise.resolve();
        }

        if (!hasWeekChanged) {
            return updateCurrentMetadataRow(userId, metadataRow.id, currentWeekInfo);
        }

        return archivePreviousWeek(userId, storedWeekInfo, currentRunRows)
            .then(function () {
                return clearCurrentWeekRuns(userId);
            })
            .then(function () {
                return updateCurrentMetadataRow(userId, metadataRow.id, currentWeekInfo);
            });
    }

    function buildViews(metadataRow, currentRunRows, archivedRows) {
        var currentWeekInfo = getWeekInfoFromMetadataRow(metadataRow) || popupState.currentWeekInfo || getWeekInfo(new Date());
        popupState.currentWeekInfo = currentWeekInfo;

        var currentView = {
            key: 'current',
            title: DEFAULT_WATCHLIST,
            selectLabel: DEFAULT_WATCHLIST + ' (' + currentWeekInfo.label + ')',
            weekLabel: currentWeekInfo.label,
            type: 'current',
            isEditable: true,
            maxItems: CURRENT_WEEK_LIMIT,
            items: currentRunRows.map(function (row) {
                return {
                    id: row.id,
                    run_key: row.run_key || '',
                    Job: row.job || '',
                    Milestone: row.milestone || '',
                    Block: row.block || '',
                    Stage: row.stage || '',
                    Dft_release: row.dft_release || '',
                    User: row.tracker_user || '',
                    Status: row.run_status || '',
                    Comments: row.comments || '',
                    Promote: row.promote || '',
                    payload: safeJsonParse(row.run_payload, {})
                };
            })
        };

        var archiveMap = {};

        archivedRows.forEach(function (row) {
            var weekKey = row.week_key || 'unknown';
            if (!archiveMap[weekKey]) {
                archiveMap[weekKey] = {
                    key: 'archive:' + weekKey,
                    title: DEFAULT_WATCHLIST + ' Archive',
                    selectLabel: (row.week_label || weekKey) + ' (Archived)',
                    weekLabel: row.week_label || weekKey,
                    type: 'archive',
                    isEditable: false,
                    maxItems: 0,
                    sortStart: row.week_start || '',
                    items: []
                };
            }

            archiveMap[weekKey].items.push({
                id: row.id,
                run_key: row.run_key || '',
                Job: row.job || '',
                Milestone: row.milestone || '',
                Block: row.block || '',
                Stage: row.stage || '',
                Dft_release: row.dft_release || '',
                User: row.tracker_user || '',
                Status: row.run_status || '',
                Comments: row.comments || '',
                Promote: row.promote || '',
                payload: safeJsonParse(row.run_payload, {})
            });
        });

        var archiveViews = Object.keys(archiveMap)
            .map(function (weekKey) {
                return archiveMap[weekKey];
            })
            .sort(function (left, right) {
                return String(right.sortStart || '').localeCompare(String(left.sortStart || ''));
            });

        popupState.views = [currentView].concat(archiveViews);
        syncSelectedView();
    }

    function loadViews(message) {
        popupState.isLoading = true;
        popupState.currentWeekInfo = getWeekInfo(new Date());

        if (message) {
            popupState.statusMessage = message;
            popupState.statusIsError = false;
        }

        renderPopup();

        return ensurePopupStateUser()
            .then(function (userId) {
                return ensureWatchlistTable()
                    .then(function () {
                        return ensureWeeklyArchiveTable();
                    })
                    .then(function () {
                        return ensureCurrentWeekMetadata(userId, popupState.currentWeekInfo);
                    })
                    .then(function (metadataRow) {
                        return fetchCurrentRunRows(userId).then(function (currentRunRows) {
                            return rolloverWeekIfNeeded(userId, metadataRow, currentRunRows, popupState.currentWeekInfo)
                                .then(function () {
                                    return Promise.all([
                                        fetchCurrentMetadataRow(userId),
                                        fetchCurrentRunRows(userId),
                                        fetchArchivedRows(userId)
                                    ]);
                                });
                        });
                    });
            })
            .then(function (results) {
                buildViews(results[0], results[1], results[2]);
                popupState.isLoading = false;
                popupState.statusMessage = message || '';
                popupState.statusIsError = false;
                renderPopup();
                return results;
            })
            .catch(function (error) {
                popupState.isLoading = false;
                popupState.statusMessage = error.message;
                popupState.statusIsError = true;
                renderPopup();
                throw error;
            });
    }

    function touchCurrentMetadata() {
        return ensurePopupStateUser()
            .then(function (userId) {
                return fetchCurrentMetadataRow(userId).then(function (metadataRow) {
                    if (!metadataRow) {
                        return insertCurrentMetadataRow(userId, popupState.currentWeekInfo || getWeekInfo(new Date()));
                    }

                    return updateCurrentMetadataRow(userId, metadataRow.id, popupState.currentWeekInfo || getWeekInfo(new Date()));
                });
            });
    }

    function addSelectedRun() {
        var normalizedRun;
        var selectedView = findView(popupState.selectedViewKey);

        try {
            normalizedRun = normalizeRun(popupState.activeRow);
        } catch (error) {
            setStatus(error.message, true);
            return;
        }

        if (!selectedView || !selectedView.isEditable) {
            setStatus('Switch back to the current APR Weekly view to edit runs.', true);
            return;
        }

        if (selectedView.items.length >= CURRENT_WEEK_LIMIT) {
            setStatus('APR Weekly can only hold 3 runs for the current week.', true);
            return;
        }

        var duplicate = selectedView.items.some(function (item) {
            return item.run_key === normalizedRun.run_key;
        });
        if (duplicate) {
            setStatus('Run already exists in APR Weekly.', true);
            return;
        }

        popupState.isLoading = true;
        setStatus('Adding selected run...', false);

        ensurePopupStateUser()
            .then(function (userId) {
                var timestamp = nowIso();

                return requestTableApi('/api/insert-record', {
                    db_location: DB_LOCATION,
                    table_name: WATCHLIST_TABLE,
                    record: {
                        record_type: RUN_RECORD,
                        user_id: userId,
                        watchlist_name: DEFAULT_WATCHLIST,
                        is_default: 1,
                        run_key: normalizedRun.run_key,
                        job: normalizedRun.Job,
                        milestone: normalizedRun.Milestone,
                        block: normalizedRun.Block,
                        stage: normalizedRun.Stage,
                        tracker_user: normalizedRun.User,
                        dft_release: normalizedRun.Dft_release,
                        run_status: normalizedRun.Status,
                        comments: normalizedRun.Comments,
                        promote: normalizedRun.Promote,
                        run_payload: JSON.stringify(popupState.activeRow || {}),
                        created_at: timestamp,
                        updated_at: timestamp
                    }
                });
            })
            .then(function () {
                return touchCurrentMetadata();
            })
            .then(function () {
                return loadViews('Run added to APR Weekly.');
            })
            .catch(function (error) {
                popupState.isLoading = false;
                setStatus(error.message, true);
            });
    }

    function removeRun(itemId) {
        var popup = ensurePopupWindow();
        var selectedView = findView(popupState.selectedViewKey);

        if (!popup || !selectedView || !selectedView.isEditable) {
            setStatus('Archived weekly snapshots are read-only.', true);
            return;
        }

        if (!popup.confirm('Remove this run from APR Weekly?')) {
            return;
        }

        popupState.isLoading = true;
        setStatus('Removing run...', false);

        ensurePopupStateUser()
            .then(function (userId) {
                return requestTableApi('/api/delete-record', {
                    db_location: DB_LOCATION,
                    table_name: WATCHLIST_TABLE,
                    criteria: {
                        id: itemId,
                        user_id: userId,
                        record_type: RUN_RECORD
                    }
                });
            })
            .then(function () {
                return touchCurrentMetadata();
            })
            .then(function () {
                return loadViews('Run removed from APR Weekly.');
            })
            .catch(function (error) {
                popupState.isLoading = false;
                setStatus(error.message, true);
            });
    }

    function renderRunsTable(view) {
        var items = view ? view.items || [] : [];

        if (!items.length) {
            return '<div class="apr-watchlist-empty">No runs saved for this weekly view yet.</div>';
        }

        var rowsHtml = '';

        items.forEach(function (item, index) {
            rowsHtml +=
                '<tr>' +
                '<td>' + escapeHtml(item.Block) + '</td>' +
                '<td>' +
                '<strong>' + escapeHtml(item.Job) + '</strong><br>' +
                '<span>' + escapeHtml(item.Milestone) + '</span>' +
                '</td>' +
                '<td>' + escapeHtml(item.Stage) + '</td>' +
                '<td>' + escapeHtml(item.Status) + '</td>' +
                '<td>' + escapeHtml(item.User) + '</td>' +
                '<td>' +
                (view.isEditable
                    ? '<button type="button" class="apr-watchlist-button danger apr-remove-run" data-item-index="' + escapeHtml(index) + '">Remove</button>'
                    : '<span class="apr-watchlist-pill archive">Archived</span>') +
                '</td>' +
                '</tr>';
        });

        return (
            '<div class="apr-watchlist-table-wrap">' +
            '<table class="apr-watchlist-table">' +
            '<thead>' +
            '<tr>' +
            '<th>Block</th>' +
            '<th>Run</th>' +
            '<th>Stage</th>' +
            '<th>Status</th>' +
            '<th>User</th>' +
            '<th></th>' +
            '</tr>' +
            '</thead>' +
            '<tbody>' + rowsHtml + '</tbody>' +
            '</table>' +
            '</div>'
        );
    }

    function renderPopup() {
        var popup = ensurePopupWindow();
        if (!popup) return;

        var doc = popup.document;
        if (!doc.getElementById('apr-watchlist-root')) {
            buildPopupShell(doc);
        }

        var root = doc.getElementById('apr-watchlist-root');
        if (!root) return;

        var selectedView = findView(popupState.selectedViewKey);
        var viewOptionsHtml = '';

        popupState.views.forEach(function (view) {
            var isSelected = view.key === popupState.selectedViewKey ? ' selected' : '';
            viewOptionsHtml += '<option value="' + escapeHtml(view.key) + '"' + isSelected + '>' + escapeHtml(view.selectLabel) + '</option>';
        });

        var statusClass = popupState.statusIsError ? 'apr-watchlist-status error' : 'apr-watchlist-status';
        var rowLabel = popupState.activeRow ? getRowLabel(popupState.activeRow) : 'No APR run selected yet.';
        var isEditableView = selectedView ? selectedView.isEditable : false;
        var addDisabled = popupState.isLoading || !popupState.activeRow || !isEditableView;
        var currentCountText = selectedView && selectedView.isEditable ? (selectedView.items.length + ' / ' + CURRENT_WEEK_LIMIT + ' runs used') : 'Read-only snapshot';

        root.innerHTML =
            '<div class="apr-watchlist-card">' +
            '<div class="apr-watchlist-header">' +
            '<div>' +
            '<h1 class="apr-watchlist-title">APR Weekly</h1>' +
            '<p class="apr-watchlist-subtitle">Current week stays editable in <code>apr_watchlist</code>. When a new week is detected, the prior week is copied into <code>apr_weekly</code> and the current list is reset.</p>' +
            '</div>' +
            '<div class="apr-watchlist-toolbar">' +
            '<button type="button" class="apr-watchlist-button secondary" id="apr-watchlist-refresh"' + (popupState.isLoading ? ' disabled' : '') + '>Refresh</button>' +
            '<button type="button" class="apr-watchlist-button" id="apr-watchlist-add"' + (addDisabled ? ' disabled' : '') + '>Add Selected Run</button>' +
            '</div>' +
            '</div>' +
            '<div class="' + statusClass + '">' + escapeHtml(popupState.statusMessage || (popupState.isLoading ? 'Loading weekly watchlists...' : '')) + '</div>' +
            '<div class="apr-watchlist-grid">' +
            '<div class="apr-watchlist-stack">' +
            '<section class="apr-watchlist-card">' +
            '<h2 class="apr-watchlist-panel-title">Selected APR Run</h2>' +
            '<div class="apr-watchlist-run">' +
            '<strong>' + escapeHtml(rowLabel) + '</strong>' +
            '<div class="apr-watchlist-meta">' +
            '<span><b>Status:</b> ' + escapeHtml((popupState.activeRow || {}).Status || '-') + '</span>' +
            '<span><b>User:</b> ' + escapeHtml((popupState.activeRow || {}).User || '-') + '</span>' +
            '<span><b>Release:</b> ' + escapeHtml((popupState.activeRow || {}).Dft_release || '-') + '</span>' +
            '<span><b>Comments:</b> ' + escapeHtml((popupState.activeRow || {}).Comments || '-') + '</span>' +
            '</div>' +
            '</div>' +
            '</section>' +
            '<section class="apr-watchlist-card">' +
            '<h2 class="apr-watchlist-panel-title">Weekly View</h2>' +
            '<div class="apr-watchlist-controls">' +
            '<select id="apr-watchlist-select" class="apr-watchlist-select"' + (popupState.isLoading ? ' disabled' : '') + '>' +
            viewOptionsHtml +
            '</select>' +
            '<div class="apr-watchlist-pill-row">' +
            (selectedView && selectedView.isEditable
                ? '<span class="apr-watchlist-pill current">Editable Current Week</span>'
                : '<span class="apr-watchlist-pill archive">Archived Snapshot</span>') +
            (selectedView ? '<span class="apr-watchlist-pill">' + escapeHtml(selectedView.weekLabel || '') + '</span>' : '') +
            '<span class="apr-watchlist-pill">' + escapeHtml(currentCountText) + '</span>' +
            '</div>' +
            '<p class="apr-watchlist-note">' +
            'APR Weekly allows up to 3 runs in the active week. Archived weekly snapshots are view-only and are kept in <code>apr_weekly</code>.' +
            '</p>' +
            '</div>' +
            '</section>' +
            '</div>' +
            '<section class="apr-watchlist-card">' +
            '<h2 class="apr-watchlist-panel-title">' + escapeHtml(selectedView ? selectedView.selectLabel : 'Weekly Runs') + '</h2>' +
            renderRunsTable(selectedView) +
            '</section>' +
            '</div>' +
            '</div>';

        var selectEl = doc.getElementById('apr-watchlist-select');
        if (selectEl) {
            selectEl.addEventListener('change', function (event) {
                popupState.selectedViewKey = event.target.value;
                renderPopup();
            });
        }

        var refreshEl = doc.getElementById('apr-watchlist-refresh');
        if (refreshEl) {
            refreshEl.addEventListener('click', function () {
                loadViews('Refreshing weekly watchlists...');
            });
        }

        var addEl = doc.getElementById('apr-watchlist-add');
        if (addEl) {
            addEl.addEventListener('click', addSelectedRun);
        }

        Array.prototype.slice.call(doc.querySelectorAll('.apr-remove-run')).forEach(function (button) {
            button.addEventListener('click', function () {
                var view = findView(popupState.selectedViewKey);
                var itemIndex = Number(button.getAttribute('data-item-index'));
                var item = view && view.items ? view.items[itemIndex] : null;

                if (!item) {
                    setStatus('Watchlist item not found.', true);
                    return;
                }

                removeRun(item.id);
            });
        });
    }

    function openWatchlistWindow(row) {
        popupState.activeRow = row || null;
        popupState.selectedViewKey = 'current';

        if (!ensurePopupWindow()) {
            return;
        }

        popupState.statusMessage = popupState.activeRow ? 'Selected run updated. You can add it to the current APR Weekly list.' : popupState.statusMessage;
        popupState.statusIsError = false;
        renderPopup();

        loadViews(popupState.statusMessage).catch(function () {
            return null;
        });

        if (popupWindow && !popupWindow.closed) {
            popupWindow.focus();
        }
    }

    window.APR_BUTTONS.push({
        id: 'watchlist',
        label: 'Watchlist',
        className: 'ui mini button',
        handler: function (row) {
            openWatchlistWindow(row);
        }
    });
})();
