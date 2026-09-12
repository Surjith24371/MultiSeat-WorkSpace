/**
 * modal.js
 * Manages the Hold & Confirm modal dialog, collaborator chip tag inputs,
 * and the floating toast notification system.
 */

import { HoldTimer } from './timer.js';

export class BookingModal {
    constructor(callbacks = {}) {
        this.callbacks = {
            onConfirm: callbacks.onConfirm || (() => {}),
            onCancel: callbacks.onCancel || (() => {}),
            onExpire: callbacks.onExpire || (() => {})
        };

        this.timer = new HoldTimer();
        this.currentSlot = null;
        this.collaborators = [];

        this.dom = {
            overlay: document.getElementById('bookingModalOverlay'),
            modal: document.getElementById('bookingModal'),
            title: document.getElementById('modalResourceTitle'),
            badge: document.getElementById('modalResourceBadge'),
            dateSlot: document.getElementById('modalDateSlot'),
            timerDigits: document.getElementById('modalTimerDigits'),
            timerBar: document.getElementById('modalTimerProgress'),
            timerContainer: document.getElementById('modalTimerContainer'),
            agendaInput: document.getElementById('modalAgendaInput'),
            collabInput: document.getElementById('modalCollabInput'),
            collabList: document.getElementById('modalCollabChips'),
            quickAddChips: document.getElementById('quickAddChips'),
            confirmBtn: document.getElementById('modalConfirmBtn'),
            cancelBtn: document.getElementById('modalCancelBtn'),
            closeBtn: document.getElementById('modalCloseBtn'),
            toastContainer: document.getElementById('toastContainer')
        };

        this.bindEvents();
    }

    bindEvents() {
        // Close / Cancel hold
        if (this.dom.closeBtn) {
            this.dom.closeBtn.addEventListener('click', () => this.handleCancelClick());
        }
        if (this.dom.cancelBtn) {
            this.dom.cancelBtn.addEventListener('click', () => this.handleCancelClick());
        }

        // Click outside modal backdrop
        if (this.dom.overlay) {
            this.dom.overlay.addEventListener('click', (e) => {
                if (e.target === this.dom.overlay) {
                    this.handleCancelClick();
                }
            });
        }

        // Confirm
        if (this.dom.confirmBtn) {
            this.dom.confirmBtn.addEventListener('click', () => this.handleConfirmClick());
        }

        // Collaborator input: Enter or comma adds tag
        if (this.dom.collabInput) {
            this.dom.collabInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    this.addCollaboratorFromInput();
                }
            });
            this.dom.collabInput.addEventListener('blur', () => {
                this.addCollaboratorFromInput();
            });
        }

        // Quick add collaborator buttons
        if (this.dom.quickAddChips) {
            this.dom.quickAddChips.addEventListener('click', (e) => {
                const btn = e.target.closest('.quick-collab-btn');
                if (btn && btn.dataset.email) {
                    this.addCollaborator(btn.dataset.email);
                }
            });
        }
    }

    open(slotData, expiresAt, durationSeconds = 90) {
        this.currentSlot = slotData;
        this.collaborators = [];

        // Fill slot details
        if (this.dom.title) {
            this.dom.title.textContent = slotData.resource_name || 'Resource Slot';
        }
        if (this.dom.badge) {
            this.dom.badge.textContent = `${slotData.icon || '📍'} ${slotData.capacity ? slotData.capacity + ' seats' : 'Resource'}`;
        }
        if (this.dom.dateSlot) {
            this.dom.dateSlot.textContent = `📅 ${slotData.booking_date}  •  ⏰ ${slotData.time_slot}`;
        }

        // Reset form
        if (this.dom.agendaInput) {
            this.dom.agendaInput.value = '';
            this.dom.agendaInput.focus();
        }
        if (this.dom.collabInput) {
            this.dom.collabInput.value = '';
        }
        this.renderCollaboratorChips();
        this.setConfirmLoading(false);

        // Show modal
        if (this.dom.overlay) {
            this.dom.overlay.classList.remove('hidden');
            this.dom.overlay.setAttribute('aria-hidden', 'false');
        }

        // Start Countdown
        this.timer.start(
            expiresAt,
            durationSeconds,
            (tickData) => this.onTimerTick(tickData),
            () => this.onTimerExpire()
        );
    }

    close() {
        this.timer.stop();
        if (this.dom.overlay) {
            this.dom.overlay.classList.add('hidden');
            this.dom.overlay.setAttribute('aria-hidden', 'true');
        }
        this.currentSlot = null;
    }

    isOpen() {
        return this.dom.overlay && !this.dom.overlay.classList.contains('hidden');
    }

    onTimerTick({ remainingSeconds, formattedTime, percent, isUrgent }) {
        if (this.dom.timerDigits) {
            this.dom.timerDigits.textContent = formattedTime;
        }
        if (this.dom.timerBar) {
            this.dom.timerBar.style.width = `${percent}%`;
            if (isUrgent) {
                this.dom.timerBar.classList.add('urgent');
                this.dom.timerDigits.classList.add('urgent-text');
            } else {
                this.dom.timerBar.classList.remove('urgent');
                this.dom.timerDigits.classList.remove('urgent-text');
            }
        }
    }

    onTimerExpire() {
        this.showToast(
            'Hold Expired',
            'Your 90-second temporary hold has expired. The slot has been released back to available.',
            'warning'
        );
        this.close();
        if (this.callbacks.onExpire) {
            this.callbacks.onExpire(this.currentSlot);
        }
    }

    addCollaboratorFromInput() {
        if (!this.dom.collabInput) return;
        const val = this.dom.collabInput.value.trim().replace(/,/g, '');
        if (val) {
            this.addCollaborator(val);
            this.dom.collabInput.value = '';
        }
    }

    addCollaborator(emailOrName) {
        const clean = emailOrName.trim();
        if (!clean) return;
        if (!this.collaborators.includes(clean)) {
            this.collaborators.push(clean);
            this.renderCollaboratorChips();
        }
    }

    removeCollaborator(index) {
        this.collaborators.splice(index, 1);
        this.renderCollaboratorChips();
    }

    renderCollaboratorChips() {
        if (!this.dom.collabList) return;
        this.dom.collabList.innerHTML = '';

        this.collaborators.forEach((item, idx) => {
            const chip = document.createElement('span');
            chip.className = 'collab-chip';
            chip.innerHTML = `
                <span class="chip-text">${this.escapeHtml(item)}</span>
                <button type="button" class="chip-remove" aria-label="Remove collaborator" data-index="${idx}">&times;</button>
            `;
            chip.querySelector('.chip-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                this.removeCollaborator(idx);
            });
            this.dom.collabList.appendChild(chip);
        });
    }

    setConfirmLoading(isLoading) {
        if (!this.dom.confirmBtn) return;
        if (isLoading) {
            this.dom.confirmBtn.disabled = true;
            this.dom.confirmBtn.innerHTML = '<span class="spinner-small"></span> Finalizing...';
        } else {
            this.dom.confirmBtn.disabled = false;
            this.dom.confirmBtn.innerHTML = '<span>Confirm Reservation</span> <span class="arrow-icon">→</span>';
        }
    }

    async handleConfirmClick() {
        if (!this.currentSlot) return;

        const agenda = (this.dom.agendaInput ? this.dom.agendaInput.value.trim() : '') || 'Multi-seat collaboration';
        this.setConfirmLoading(true);

        if (this.callbacks.onConfirm) {
            await this.callbacks.onConfirm({
                slot: this.currentSlot,
                agenda: agenda,
                collaborators: [...this.collaborators]
            });
        }
    }

    async handleCancelClick() {
        if (!this.currentSlot) {
            this.close();
            return;
        }

        const slotToCancel = { ...this.currentSlot };
        this.close();

        if (this.callbacks.onCancel) {
            await this.callbacks.onCancel(slotToCancel);
        }
    }

    /**
     * Floating Toast Notification
     */
    showToast(title, message, type = 'info', duration = 4500) {
        if (!this.dom.toastContainer) return;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icons = {
            success: '✅',
            warning: '⚠️',
            error: '❌',
            info: 'ℹ️'
        };

        toast.innerHTML = `
            <div class="toast-icon">${icons[type] || '🔔'}</div>
            <div class="toast-content">
                <div class="toast-title">${this.escapeHtml(title)}</div>
                <div class="toast-message">${this.escapeHtml(message)}</div>
            </div>
            <button type="button" class="toast-close" aria-label="Dismiss">&times;</button>
            <div class="toast-progress"></div>
        `;

        toast.querySelector('.toast-close').addEventListener('click', () => {
            this.dismissToast(toast);
        });

        this.dom.toastContainer.appendChild(toast);

        // Auto dismiss
        const timer = setTimeout(() => {
            this.dismissToast(toast);
        }, duration);

        toast._timer = timer;
    }

    dismissToast(toast) {
        if (!toast || toast.classList.contains('dismissing')) return;
        toast.classList.add('dismissing');
        clearTimeout(toast._timer);
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 260);
    }

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
}
