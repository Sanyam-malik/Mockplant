// Background gradient management
const getBalancedColor = () => {
    // Generate balanced colors with darker tones
    const r = Math.floor(50 + Math.random() * 205); // 50-255
    const g = Math.floor(50 + Math.random() * 205); // 50-255
    const b = Math.floor(50 + Math.random() * 205); // 50-255
    return `rgb(${r}, ${g}, ${b})`;
};

const setRandomGradient = () => {
    const colors = Array.from({ length: 4 }, () => getBalancedColor());
    document.body.style.background = `linear-gradient(-45deg, ${colors.join(', ')})`;
    document.body.style.backgroundSize = '400% 400%';
};

// Initialize gradient background
setRandomGradient();
setInterval(setRandomGradient, 15000); // Change every 15s

function autoResize(textarea) {
    textarea.style.height = 'auto'; // Reset height
    textarea.style.height = textarea.scrollHeight + 'px'; // Set to scroll height
}

function convertToText(content) {
    return `${content}`;
}

// Content sanitization helpers
function sanitizeContent(content, contentType) {
    if (!content) return '';

    switch (contentType) {
        case 'text/html':
        case 'application/xml':
            return escapeHtml(content);
        case 'text/css':
            return escapeCss(content);
        case 'application/javascript':
            return escapeJs(content);
        case 'application/json':
            try {
                // For JSON, we want to preserve the structure but escape any HTML in string values
                const parsed = JSON.parse(content);
                return JSON.stringify(parsed, (key, value) => {
                    if (typeof value === 'string') {
                        return escapeHtml(value);
                    }
                    return value;
                });
            } catch (e) {
                return escapeHtml(content);
            }
        default:
            return escapeHtml(content);
    }
}

function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function escapeCss(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/</g, "\\3C ")
        .replace(/>/g, "\\3E ")
        .replace(/"/g, "\\22")
        .replace(/'/g, "\\27")
        .replace(/&/g, "\\26");
}

function escapeJs(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .replace(/</g, "\\u003C")
        .replace(/>/g, "\\u003E")
        .replace(/"/g, "\\u0022")
        .replace(/'/g, "\\u0027")
        .replace(/&/g, "\\u0026");
}