function showLoader(txt) {
    const loaderText = txt || "Loading...";
    document.getElementById("loader-txt").textContent = loaderText;
    document.getElementById("loader").style.display = "flex";
}

function hideLoader() {
    document.getElementById("loader").style.display = "none";
}

// Utility functions
function showCommonModal({
    title,
    message,
    type = 'primary',
    confirmText = 'OK',
    cancelText = null,
    onConfirm = null,
    onCancel = null,
    size = 'md'
}) {
    const modalHtml = `
        <div class="modal fade" id="commonModal" tabindex="-1" aria-labelledby="commonModalLabel" aria-hidden="true">
            <div class="modal-dialog modal-${size}">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title" id="commonModalLabel">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        ${message}
                    </div>
                    <div class="modal-footer">
                        ${cancelText ? `<button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelText}</button>` : ''}
                        <button type="button" class="btn btn-${type}" id="commonModalConfirmBtn">${confirmText}</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if any
    const existingModal = document.getElementById('commonModal');
    if (existingModal) {
        existingModal.remove();
    }

    // Add new modal to body
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    // Show the modal
    const modal = new bootstrap.Modal(document.getElementById('commonModal'));
    modal.show();

    // Handle confirmation
    const confirmBtn = document.getElementById('commonModalConfirmBtn');
    confirmBtn.addEventListener('click', () => {
        if (onConfirm) {
            onConfirm();
        }
        modal.hide();
    });

    // Handle cancellation
    if (onCancel) {
        const modalElement = document.getElementById('commonModal');
        modalElement.addEventListener('hidden.bs.modal', () => {
            onCancel();
        });
    }
}

const showError = (message) => {
    showCommonModal({
        title: 'Error',
        message: message,
        type: 'danger',
        confirmText: 'OK'
    });
    console.error(message);
};