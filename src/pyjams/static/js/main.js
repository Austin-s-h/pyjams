// Global error handling
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
    // You could send this to your error tracking service
});

// Alert management
class AlertManager {
    static show(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.role = 'alert';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;
        
        const container = document.querySelector('.flash-messages');
        if (container) {
            container.appendChild(alertDiv);
            // Auto-remove after 5 seconds
            setTimeout(() => alertDiv.remove(), 5000);
        }
    }
}

// Close button handler for alerts
document.addEventListener('click', function(e) {
    if (e.target.matches('[data-dismiss="alert"], [data-dismiss="alert"] *')) {
        const alert = e.target.closest('.alert');
        if (alert) {
            alert.remove();
        }
    }
});

// Export utilities for other scripts
window.PyJams = {
    AlertManager,
    showError: (message) => AlertManager.show(message, 'danger'),
    showSuccess: (message) => AlertManager.show(message, 'success'),
    showInfo: (message) => AlertManager.show(message, 'info')
};
