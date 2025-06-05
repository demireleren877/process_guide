// Excel import form işlemleri
function initExcelImport() {
    const form = document.getElementById('excelImportForm');
    const fileInput = document.getElementById('excelFile');
    const sheetSelect = document.getElementById('sheetSelect');
    const tableSelect = document.getElementById('tableSelect');
    const createNewTableCheckbox = document.getElementById('createNewTable');
    const existingTableSection = document.getElementById('existingTableSection');
    const newTableSection = document.getElementById('newTableSection');
    const newTableNameInput = document.getElementById('newTableName');
    const columnMappingSection = document.getElementById('columnMappingSection');
    const columnMappingBody = document.getElementById('columnMappingBody');
    const previewInfo = document.getElementById('previewInfo');
    const previewContent = document.getElementById('previewContent');
    const errorAlert = document.getElementById('errorAlert');
    const successAlert = document.getElementById('successAlert');
    const importButton = document.getElementById('importButton');
    
    let excelColumns = [];
    let oracleColumns = [];
    let columnTypes = {};
    
    // Excel dosyası seçildiğinde
    fileInput.addEventListener('change', function() {
        if (this.files.length > 0) {
            const formData = new FormData();
            formData.append('file', this.files[0]);
            
            fetch('/api/excel/sheets', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    sheetSelect.innerHTML = '<option value="">Sayfa seçin</option>' +
                        data.sheets.map(sheet => `<option value="${sheet}">${sheet}</option>`).join('');
                    sheetSelect.disabled = false;
                    checkImportButtonState();
                } else {
                    showError('Sayfalar yüklenirken hata oluştu: ' + data.error);
                }
            })
            .catch(error => {
                showError('Sayfalar yüklenirken hata oluştu: ' + error);
            });
        }
    });

    // Form gönderildiğinde
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (!fileInput.files.length || !sheetSelect.value) {
            showError('Lütfen Excel dosyası ve sayfa seçin');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('sheet_name', sheetSelect.value);
        
        // Sütun eşleştirme bilgilerini topla
        const columnMappings = [];
        const rows = columnMappingBody.getElementsByTagName('tr');
        for (const row of rows) {
            const includeCheckbox = row.cells[3].querySelector('input[type="checkbox"]');
            if (includeCheckbox.checked) {
                const excelCol = row.cells[0].textContent;
                let oracleCol, oracleType;
                
                if (createNewTableCheckbox.checked) {
                    oracleCol = row.cells[1].textContent;
                    oracleType = row.cells[2].querySelector('select').value;
                } else {
                    const oracleCell = row.cells[1];
                    if (oracleCell.querySelector('select')) {
                        const oracleSelect = oracleCell.querySelector('select');
                        if (!oracleSelect.value) {
                            showError(`Lütfen "${excelCol}" sütunu için bir Oracle sütunu seçin`);
                            return;
                        }
                        oracleCol = oracleSelect.value;
                    } else {
                        oracleCol = oracleCell.textContent;
                    }
                    oracleType = row.cells[2].querySelector('select').value;
                }
                
                columnMappings.push({
                    excel_column: excelCol,
                    oracle_column: oracleCol,
                    oracle_type: oracleType,
                    handle_null: true
                });
            }
        }
        
        formData.append('column_mappings', JSON.stringify(columnMappings));
        
        if (createNewTableCheckbox.checked) {
            const newTableName = newTableNameInput.value.trim();
            if (!newTableName) {
                showError('Lütfen yeni tablo adını girin');
                return;
            }
            formData.append('create_new_table', 'true');
            formData.append('new_table_name', newTableName);
        } else {
            if (!tableSelect.value) {
                showError('Lütfen hedef tabloyu seçin');
                return;
            }
            formData.append('table_name', tableSelect.value);
            const importMode = document.querySelector('input[name="importMode"]:checked').value;
            formData.append('import_mode', importMode);
        }
        
        importButton.disabled = true;
        importButton.querySelector('.spinner-border').style.display = 'inline-block';
        
        fetch('/api/excel/import', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                let message = data.message;
                if (data.column_mapping) {
                    message += '<br><br>Sütun Eşleştirmeleri:<br>';
                    for (const [excel, oracle] of Object.entries(data.column_mapping)) {
                        message += `${excel} → ${oracle}<br>`;
                    }
                }
                showSuccess(message);
                // Form alanlarını sıfırla
                fileInput.value = '';
                sheetSelect.innerHTML = '<option value="">Önce Excel dosyası seçin</option>';
                sheetSelect.disabled = true;
                newTableNameInput.value = '';
                columnMappingSection.style.display = 'none';
                importButton.disabled = true;
                // Başarı mesajını 5 saniye sonra gizle
                setTimeout(() => {
                    successAlert.style.display = 'none';
                    // Modalı kapat
                    const modal = bootstrap.Modal.getInstance(document.getElementById('excelImportModal'));
                    modal.hide();
                }, 5000);
            } else {
                showError(data.error);
            }
        })
        .catch(error => {
            showError('İçe aktarma sırasında hata oluştu: ' + error);
        })
        .finally(() => {
            importButton.disabled = false;
            importButton.querySelector('.spinner-border').style.display = 'none';
        });
    });
    
    // Oracle tablolarını yükle
    function loadOracleTables() {
        fetch('/api/oracle/tables')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    tableSelect.innerHTML = '<option value="">Tablo seçin</option>' +
                        data.tables.map(table => `<option value="${table}">${table}</option>`).join('');
                    checkImportButtonState();
                } else {
                    showError('Tablolar yüklenirken hata oluştu: ' + data.error);
                }
            })
            .catch(error => {
                showError('Tablolar yüklenirken hata oluştu: ' + error);
            });
    }

    // Modal açıldığında tabloları yükle
    document.getElementById('excelImportModal').addEventListener('show.bs.modal', function () {
        loadOracleTables();
    });

    function showError(message) {
        errorAlert.innerHTML = message;
        errorAlert.style.display = 'block';
        successAlert.style.display = 'none';
    }

    function showSuccess(message) {
        successAlert.innerHTML = message;
        successAlert.style.display = 'block';
        errorAlert.style.display = 'none';
    }

    function checkImportButtonState() {
        const hasFile = fileInput.files.length > 0;
        const hasSheet = sheetSelect.value !== '';
        const hasTable = createNewTableCheckbox.checked ? newTableNameInput.value.trim() !== '' : tableSelect.value !== '';
        importButton.disabled = !(hasFile && hasSheet && hasTable);
    }

    // Event listeners for form validation
    sheetSelect.addEventListener('change', checkImportButtonState);
    tableSelect.addEventListener('change', checkImportButtonState);
    newTableNameInput.addEventListener('input', checkImportButtonState);
    createNewTableCheckbox.addEventListener('change', function() {
        existingTableSection.style.display = this.checked ? 'none' : 'block';
        newTableSection.style.display = this.checked ? 'block' : 'none';
        checkImportButtonState();
    });
}

// Export the initialization function
window.initExcelImport = initExcelImport; 