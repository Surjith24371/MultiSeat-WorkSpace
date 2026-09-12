/**
 * main.js
 * Central Application Controller.
 * Manages user persona switching, date picking, 5-second auto-polling,
 * quota meters, and coordinates the ResourceGrid, BookingModal, and API service.
 */

import { API } from './api.js';
import { ResourceGrid } from './grid.js';
import { BookingModal } from './modal.js';
import { MOCK_USERS } from '../mocks/mockData.js';

class WorkspaceApp {
    constructor() {
        // App State
        this.todayStr = new Date().toISOString().split('T')[0];
        this.selectedDate = this.todayStr;
        this.currentUserId = MOCK_USERS[0].id;
        this.activeQuota = { used_hours: 0, max_hours: 3, remaining_hours: 3 };
        this.pollingIntervalMs = 5000;
        this.pollTimerId = null;
        this.isFetching = false;

        // UI Components
        this.grid = new ResourceGrid('matrixContainer', (slot) => this.handleSlotClick(slot));
        this.modal = new BookingModal({
            onConfirm: (data) => this.handleConfirm(data),
            onCancel: (slot) => this.handleCancel(slot),
            onExpire: (slot) => this.handleExpire(slot)
        });

        // DOM elements
        this.dom = {
            datePicker: document.getElementById('bookingDatePicker'),
            userSelect: document.getElementById('userPersonaSelect'),
            userAvatar: document.getElementById('userAvatar'),
            userRole: document.getElementById('userRoleText'),
            quotaUsedBadge: document.getElementById('quotaUsedBadge'),
            quotaBarFill: document.getElementById('quotaBarFill'),
            refreshBtn: document.getElementById('manualRefreshBtn'),
            refreshIcon: document.getElementById('refreshIcon'),
            modeToggleBtn: document.getElementById('modeToggleBtn'),
            modeBadge: document.getElementById('modeBadgeText'),
            quickDateBtns: document.querySelectorAll('.quick-date-btn')
        };
    }

    init() {
        this.setupUserPersonas();
        this.setupDatePicker();
        this.setupModeToggle();
        this.setupRefreshButton();
        this.setupQuickDateButtons();

        // Initial Data Fetch
        this.fetchAvailability(true);

        // Start 5-Second Real-Time Auto-Polling
        this.startAutoPolling();
    }

    setupUserPersonas() {
        if (!this.dom.userSelect) return;
        this.dom.userSelect.innerHTML = '';

        MOCK_USERS.forEach(user => {
            const opt = document.createElement('option');
            opt.value = user.id;
            opt.textContent = `${user.avatar} ${user.name} (${user.role})`;
            this.dom.userSelect.appendChild(opt);
        });

        this.dom.userSelect.value = this.currentUserId;
        this.updateUserMetaDisplay();

        this.dom.userSelect.addEventListener('change', (e) => {
            this.currentUserId = e.target.value;
            this.updateUserMetaDisplay();
            this.fetchAvailability(false);
            this.modal.showToast('User Switched', `Active session: ${this.getCurrentUser().name}`, 'info', 2500);
        });
    }

    getCurrentUser() {
        return MOCK_USERS.find(u => u.id === this.currentUserId) || MOCK_USERS[0];
    }

    updateUserMetaDisplay() {
        const user = this.getCurrentUser();
        if (this.dom.userAvatar) this.dom.userAvatar.textContent = user.avatar;
        if (this.dom.userRole) this.dom.userRole.textContent = user.role;
    }

    setupDatePicker() {
        if (!this.dom.datePicker) return;
        this.dom.datePicker.value = this.selectedDate;
        this.dom.datePicker.min = this.todayStr;

        this.dom.datePicker.addEventListener('change', (e) => {
            this.selectedDate = e.target.value || this.todayStr;
            this.updateQuickDateActiveState();
            this.fetchAvailability(true);
        });
    }

    setupQuickDateButtons() {
        this.dom.quickDateBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const offsetDays = parseInt(btn.dataset.offset || '0', 10);
                const targetDate = new Date();
                targetDate.setDate(targetDate.getDate() + offsetDays);
                this.selectedDate = targetDate.toISOString().split('T')[0];

                if (this.dom.datePicker) {
                    this.dom.datePicker.value = this.selectedDate;
                }
                this.updateQuickDateActiveState();
                this.fetchAvailability(true);
            });
        });
    }

    updateQuickDateActiveState() {
        this.dom.quickDateBtns.forEach(btn => {
            const offsetDays = parseInt(btn.dataset.offset || '0', 10);
            const targetDate = new Date();
            targetDate.setDate(targetDate.getDate() + offsetDays);
            const str = targetDate.toISOString().split('T')[0];
            if (str === this.selectedDate) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }

    setupModeToggle() {
        if (!this.dom.modeToggleBtn) return;

        this.dom.modeToggleBtn.addEventListener('click', () => {
            const nextModeIsMock = !API.isMock();
            API.setMockMode(nextModeIsMock);
            this.updateModeBadge();
            this.fetchAvailability(true);
            this.modal.showToast(
                'API Mode Changed',
                nextModeIsMock ? 'Using In-Memory Mock Engine' : 'Connected to Live Flask Server',
                nextModeIsMock ? 'info' : 'success'
            );
        });

        this.updateModeBadge();
    }

    updateModeBadge() {
        if (!this.dom.modeBadge) return;
        const isMock = API.isMock();
        this.dom.modeBadge.textContent = isMock ? 'Mode: Simulated Mock' : 'Mode: Live Backend';
        if (isMock) {
            this.dom.modeBadge.classList.add('badge-mock');
            this.dom.modeBadge.classList.remove('badge-live');
        } else {
            this.dom.modeBadge.classList.remove('badge-mock');
            this.dom.modeBadge.classList.add('badge-live');
        }
    }

    setupRefreshButton() {
        if (!this.dom.refreshBtn) return;
        this.dom.refreshBtn.addEventListener('click', () => {
            if (this.dom.refreshIcon) {
                this.dom.refreshIcon.classList.add('rotating');
            }
            this.fetchAvailability(false).finally(() => {
                setTimeout(() => {
                    if (this.dom.refreshIcon) {
                        this.dom.refreshIcon.classList.remove('rotating');
                    }
                }, 400);
            });
        });
    }

    startAutoPolling() {
        if (this.pollTimerId) clearInterval(this.pollTimerId);

        this.pollTimerId = setInterval(() => {
            // Avoid disrupting active form filling in modal
            if (!this.modal.isOpen()) {
                this.fetchAvailability(false);
            }
        }, this.pollingIntervalMs);
    }

    stopAutoPolling() {
        if (this.pollTimerId) {
            clearInterval(this.pollTimerId);
            this.pollTimerId = null;
        }
    }

    /**
     * Fetch availability data from API
     */
    async fetchAvailability(showLoader = false) {
        if (this.isFetching) return;
        this.isFetching = true;

        if (showLoader) {
            this.grid.showLoading(true);
        }

        try {
            const res = await API.getAvailability(this.selectedDate, this.currentUserId);

            if (res.status === 200 && res.data) {
                const slots = Array.isArray(res.data) ? res.data : (res.data.slots || []);
                const quota = res.data.quota || null;

                // Render grid
                this.grid.render(slots, this.currentUserId);

                // Update quota UI
                if (quota) {
                    this.updateQuotaDisplay(quota);
                } else {
                    this.computeAndRenderQuotaFallback(slots);
                }
            } else if (res.status === 0) {
                // Network failure
                if (showLoader) {
                    this.modal.showToast(
                        'Backend Disconnected',
                        'Could not connect to Flask API. Switching to Offline Mock Mode.',
                        'warning',
                        4000
                    );
                    API.setMockMode(true);
                    this.updateModeBadge();
                    this.fetchAvailability(true);
                }
            }
        } catch (err) {
            console.error('[Main] Availability fetch exception:', err);
        } finally {
            this.isFetching = false;
            if (showLoader) {
                this.grid.showLoading(false);
            }
        }
    }

    computeAndRenderQuotaFallback(slots) {
        let used = 0;
        slots.forEach(s => {
            if (s.user_id === this.currentUserId && (s.status === 'CONFIRMED' || s.status === 'HELD')) {
                used += 1;
            }
        });
        this.updateQuotaDisplay({
            used_hours: used,
            max_hours: 3,
            remaining_hours: Math.max(0, 3 - used)
        });
    }

    updateQuotaDisplay({ used_hours, max_hours, remaining_hours }) {
        this.activeQuota = { used_hours, max_hours, remaining_hours };

        if (this.dom.quotaUsedBadge) {
            this.dom.quotaUsedBadge.textContent = `${used_hours} / ${max_hours} hrs used today`;
            if (used_hours >= max_hours) {
                this.dom.quotaUsedBadge.className = 'quota-badge badge-limit';
            } else if (used_hours === max_hours - 1) {
                this.dom.quotaUsedBadge.className = 'quota-badge badge-warning';
            } else {
                this.dom.quotaUsedBadge.className = 'quota-badge badge-ok';
            }
        }

        if (this.dom.quotaBarFill) {
            const pct = Math.min(100, Math.max(0, (used_hours / max_hours) * 100));
            this.dom.quotaBarFill.style.width = `${pct}%`;
            if (used_hours >= max_hours) {
                this.dom.quotaBarFill.className = 'quota-fill fill-limit';
            } else {
                this.dom.quotaBarFill.className = 'quota-fill fill-normal';
            }
        }
    }

    /**
     * Handle slot click from matrix
     */
    async handleSlotClick(slot) {
        // If slot is held by ME, resume modal
        if (slot.status === 'HELD' && slot.user_id === this.currentUserId) {
            const expiresAt = slot.hold_expires_at || (Date.now() + 90000);
            this.modal.open(slot, expiresAt, 90);
            return;
        }

        // Only AVAILABLE slots can be clicked to hold
        if (slot.status !== 'AVAILABLE') {
            return;
        }

        // Client-side quick check on quota
        if (this.activeQuota.used_hours >= this.activeQuota.max_hours) {
            this.modal.showToast(
                'Quota Limit Reached',
                `You have reached your 3-hour daily quota for ${this.selectedDate}. Switch user or select another day.`,
                'warning',
                5000
            );
            return;
        }

        // Call POST /api/resources/hold
        this.grid.showLoading(true);
        const res = await API.placeHold(
            slot.resource_name,
            this.selectedDate,
            slot.time_slot,
            this.currentUserId
        );
        this.grid.showLoading(false);

        if (res.status === 201) {
            // Success: Open 90-second hold modal
            const expiresAt = res.data.expires_at || (Date.now() + (res.data.expires_in_seconds || 90) * 1000);
            const durationSec = res.data.expires_in_seconds || 90;

            const enrichedSlot = {
                ...slot,
                id: res.data.slot_id || slot.id,
                user_id: this.currentUserId,
                status: 'HELD'
            };

            this.modal.open(enrichedSlot, expiresAt, durationSec);
            this.modal.showToast(
                'Soft-Lock Placed',
                'You have 90 seconds to finalize agenda and invite teammates.',
                'success',
                3500
            );

            // Immediate silent refresh to show yellow cell
            this.fetchAvailability(false);
        } else if (res.status === 409) {
            // Slot already taken
            this.modal.showToast(
                'Slot Already Taken',
                res.data.message || 'Conflict: Another user just held or booked this slot.',
                'error',
                4500
            );
            this.fetchAvailability(false);
        } else if (res.status === 422) {
            // Daily Quota Exceeded
            this.modal.showToast(
                'Daily Quota Exceeded',
                res.data.message || 'A single user cannot book more than 3 cumulative hours per day.',
                'warning',
                5000
            );
            this.fetchAvailability(false);
        } else {
            // Error / Network
            this.modal.showToast(
                'Hold Failed',
                res.data.message || 'Could not place hold. Please try again.',
                'error',
                4000
            );
        }
    }

    /**
     * Handle modal confirmation
     */
    async handleConfirm({ slot, agenda, collaborators }) {
        const slotId = slot.id;
        const res = await API.confirmBooking(slotId, this.currentUserId, agenda, collaborators);

        if (res.status === 200) {
            this.modal.close();
            this.modal.showToast(
                'Reservation Confirmed! 🎉',
                `${slot.resource_name} is permanently booked for ${slot.time_slot}.`,
                'success',
                5000
            );
            await this.fetchAvailability(false);
        } else if (res.status === 410) {
            this.modal.close();
            this.modal.showToast(
                'Hold Expired',
                'Your 90-second hold expired right before confirmation. The slot has been freed.',
                'error',
                5000
            );
            await this.fetchAvailability(false);
        } else {
            this.modal.setConfirmLoading(false);
            this.modal.showToast(
                'Confirmation Error',
                res.data.message || 'Could not confirm booking.',
                'error',
                4500
            );
        }
    }

    /**
     * Handle modal cancellation
     */
    async handleCancel(slot) {
        if (!slot || !slot.id) return;
        const res = await API.cancelSlot(slot.id, this.currentUserId);

        if (res.status === 200) {
            this.modal.showToast('Hold Released', 'Slot has been made available for others.', 'info', 2500);
        }
        await this.fetchAvailability(false);
    }

    /**
     * Handle timer reaching 0
     */
    async handleExpire(slot) {
        await this.fetchAvailability(false);
    }
}

// Bootstrap on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new WorkspaceApp();
    app.init();
    window.__WORKSPACE_APP = app; // Accessible for debugging/tests
});
