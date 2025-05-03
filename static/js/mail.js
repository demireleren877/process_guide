// Mail durumu yönetimi için merkezi fonksiyonlar
class MailStatusManager {
    static async checkMailReplies(stepId) {
        const mailStatuses = document.querySelectorAll(`tr[data-step-id="${stepId}"] .mail-status, #variables-data-${stepId} .mail-status, #variablesModal .mail-status`);
        if (!mailStatuses.length) return;

        try {
            const response = await fetch(`/step/${stepId}/check-mail-replies`, {
                method: 'POST'
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    // Mail durumlarını güncelle
                    const mailStatuses = {};
                    result.mail_statuses.forEach(status => {
                        mailStatuses[status.variable_id] = status.status;
                        // Mail konfigürasyonunu güncelle
                        const statusElement = document.querySelector(`.mail-status[data-variable-id="${status.variable_id}"]`);
                        if (statusElement) {
                            // Mail durumu HTML'ini güncelle
                            let statusHtml = '';
                            if (status.status === 'received') {
                                statusHtml = `
                                    <div>
                                        <i class="bi bi-check-circle-fill"></i>
                                        <span class="status-text">Yanıt Alındı</span>
                                        ${status.replies && status.replies.length > 0 ? `
                                            <div class="reply-details mt-2">
                                                <small class="d-block text-muted">Son yanıt:</small>
                                                <div class="reply-info">
                                                    <strong>${status.replies[status.replies.length - 1].sender}</strong>
                                                    <span class="mx-1">-</span>
                                                    <span>${status.replies[status.replies.length - 1].received_at}</span>
                                                </div>
                                            </div>
                                        ` : ''}
                                    </div>
                                `;
                            } else if (status.config && status.config.active) {
                                statusHtml = `
                                    <div>
                                        <i class="bi bi-hourglass"></i>
                                        <span class="status-text">Yanıt Bekleniyor</span>
                                        ${status.config.sent_at ? `
                                            <div class="reply-details mt-2">
                                                <small class="d-block text-muted">Gönderilme:</small>
                                                <div class="reply-info">
                                                    <span>${status.config.sent_at}</span>
                                                </div>
                                            </div>
                                        ` : ''}
                                    </div>
                                `;
                            } else {
                                statusHtml = `
                                    <div>
                                        <i class="bi bi-dash-circle"></i>
                                        <span class="status-text">Pasif</span>
                                    </div>
                                `;
                            }
                            
                            // Mail durumu sınıflarını güncelle
                            statusElement.className = `mail-status me-2 ${status.status === 'received' ? 'has-reply text-success' : status.config && status.config.active ? 'no-reply text-warning' : ''}`;
                            statusElement.innerHTML = statusHtml;
                            
                            // Config verisini güncelle
                            statusElement.dataset.config = JSON.stringify(status.config);
                        }
                    });
                    
                    // Adım durumunu güncelle
                    const stepRow = document.querySelector(`tr[data-step-id="${stepId}"]`);
                    if (stepRow) {
                        const statusButton = stepRow.querySelector('.status-button');
                        if (statusButton) {
                            // Tüm mail durumlarını kontrol et
                            const allReceived = Object.values(mailStatuses).every(status => status === 'received');
                            const hasWaiting = Object.values(mailStatuses).some(status => status === 'waiting');
                            
                            if (allReceived) {
                                statusButton.className = 'btn btn-sm dropdown-toggle status-button btn-success';
                                statusButton.textContent = 'Tamamlandı';
                            } else if (hasWaiting) {
                                statusButton.className = 'btn btn-sm dropdown-toggle status-button btn-warning';
                                statusButton.textContent = 'Beklemede';
                            }
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Mail durumları kontrol edilirken hata oluştu:', error);
        }
    }

    static updateStepStatus(stepId, status, statusText) {
        const stepElement = document.querySelector(`tr[data-step-id="${stepId}"]`);
        if (stepElement) {
            const statusButton = stepElement.querySelector('.status-button');
            if (statusButton) {
                // Durum butonunun sınıflarını güncelle
                statusButton.className = `btn btn-sm dropdown-toggle status-button ${
                    status === 'done' ? 'btn-success' :
                    status === 'in_progress' ? 'btn-primary' :
                    status === 'waiting' ? 'btn-warning' :
                    'btn-secondary'
                }`;
                
                // Durum metnini güncelle
                const statusTextElement = statusButton.querySelector('.status-text');
                if (statusTextElement) {
                    statusTextElement.textContent = statusText;
                } else {
                    statusButton.textContent = statusText;
                }
            }
        }
    }

    static updateMailStatuses(stepId, mailStatuses) {
        // Her bir mail durumunu güncelle
        Object.entries(mailStatuses).forEach(([variableId, status]) => {
            const statusElements = document.querySelectorAll(`.mail-status[data-variable-id="${variableId}"]`);
            statusElements.forEach(statusElement => {
                if (statusElement) {
                    // Mail durumunu güncelle
                    statusElement.className = `mail-status me-2 ${status === 'received' ? 'has-reply text-success' : 'no-reply text-warning'}`;
                    
                    // Mail konfigürasyonunu al
                    const config = JSON.parse(statusElement.dataset.config || '{}');
                    
                    // Durum metnini güncelle
                    let statusHtml = '';
                    if (status === 'received') {
                        statusHtml = `
                            <i class="bi bi-check-circle-fill"></i>
                            <span class="status-text">Yanıt Alındı</span>
                        `;
                    } else if (config.sent_at) {
                        statusHtml = `
                            <i class="bi bi-hourglass"></i>
                            <span class="status-text">Yanıt Bekleniyor</span>
                            <div class="reply-details mt-2">
                                <small class="d-block text-muted">Gönderilme:</small>
                                <div class="reply-info">
                                    <span>${config.sent_at}</span>
                                </div>
                            </div>
                        `;
                    } else {
                        statusHtml = `
                            <i class="bi bi-envelope"></i>
                            <span class="status-text">Gönderilmedi</span>
                        `;
                    }
                    
                    statusElement.innerHTML = statusHtml;
                }
            });
        });
    }

    static markStepAsDone(stepId) {
        const stepElement = document.querySelector(`#step${stepId}`);
        if (stepElement) {
            stepElement.classList.add('completed');
            const statusBadge = stepElement.querySelector('.step-status');
            if (statusBadge) {
                statusBadge.textContent = 'Tamamlandı';
                statusBadge.className = 'badge bg-success step-status';
            }
        }
    }

    static initializeMailStatusCheck() {
        document.querySelectorAll('.check-mail-status').forEach(button => {
            button.addEventListener('click', async () => {
                const stepId = button.dataset.stepId;
                button.disabled = true;
                try {
                    await MailStatusManager.checkMailReplies(stepId);
                } finally {
                    button.disabled = false;
                }
            });
        });
    }
}

// Mail gönderme işlemi
async function sendMail(stepId) {
    const form = document.getElementById(`mailForm${stepId}`);
    const formData = new FormData(form);
    
    try {
        const response = await fetch(`/step/${stepId}/send_mail`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            const result = await response.json();
            if (result.success) {
                // Mail başarıyla gönderildi, durumu güncelle
                await MailStatusManager.checkMailReplies(stepId);
                
                // Modal'ı kapat
                const modal = bootstrap.Modal.getInstance(document.getElementById(`mailModal${stepId}`));
                modal.hide();
                
                // Başarı mesajını göster
                showAlert('success', 'Mail başarıyla gönderildi.');
                
                // Mail durumlarını güncelle
                const mailStatuses = {};
                result.mail_statuses.forEach(status => {
                    mailStatuses[status.variable_id] = status.status;
                    // Mail konfigürasyonunu güncelle
                    const statusElement = document.querySelector(`.mail-status[data-variable-id="${status.variable_id}"]`);
                    if (statusElement && status.config) {
                        statusElement.dataset.config = JSON.stringify(status.config);
                    }
                });
                MailStatusManager.updateMailStatuses(stepId, mailStatuses);
            } else {
                showAlert('error', result.error || 'Mail gönderilirken bir hata oluştu.');
            }
        } else {
            showAlert('error', 'Mail gönderilirken bir hata oluştu.');
        }
    } catch (error) {
        console.error('Mail gönderme hatası:', error);
        showAlert('error', 'Mail gönderme hatası:', error);
    }
}

// Sayfa yüklendiğinde mail durumu kontrollerini başlat
document.addEventListener('DOMContentLoaded', () => {
    MailStatusManager.initializeMailStatusCheck();
}); 