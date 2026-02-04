// Common JavaScript utilities for Medical SMM Bot

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Format all datetime elements
    formatAllDates();
});

// Confirm dangerous actions
document.querySelectorAll('[data-confirm]').forEach(function(element) {
    element.addEventListener('click', function(e) {
        const message = this.getAttribute('data-confirm');
        if (!confirm(message)) {
            e.preventDefault();
            return false;
        }
    });
});

// Format dates to Russian locale with 24-hour format (DD.MM.YYYY HH:MM)
// Handles both UTC and local datetimes from API
function formatDate(dateString) {
    if (!dateString) return '-';

    let date;

    // If the date string doesn't have timezone info (no Z or +), treat it as UTC
    if (!dateString.includes('Z') && !dateString.includes('+') && !dateString.includes('-', 10)) {
        // Naive datetime - assume UTC and convert to local
        date = new Date(dateString + 'Z');
    } else {
        // Already has timezone info
        date = new Date(dateString);
    }

    if (isNaN(date)) return dateString;

    // Get local time components
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');

    return `${day}.${month}.${year} ${hours}:${minutes}`;
}

// Format all dates on page
function formatAllDates() {
    document.querySelectorAll('[data-date]').forEach(function(element) {
        const dateString = element.getAttribute('data-date');
        element.textContent = formatDate(dateString);
    });
}

// Show loading spinner
function showLoading(button) {
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Загрузка...';
    return originalText;
}

// Hide loading spinner
function hideLoading(button, originalText) {
    button.disabled = false;
    button.innerHTML = originalText;
}

// Copy to clipboard utility
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        alert('Скопировано в буфер обмена');
    }).catch(function(err) {
        console.error('Failed to copy: ', err);
    });
}

// Format large numbers
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

// Truncate text
function truncate(text, length) {
    if (text.length <= length) return text;
    return text.substring(0, length) + '...';
}

// Debounce function for search inputs
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

console.log('Medical SMM Bot - Web Interface Loaded');
