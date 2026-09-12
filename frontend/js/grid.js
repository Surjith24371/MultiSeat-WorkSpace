/**
 * grid.js
 * Renders the interactive Resource x Hourly Time Slot Matrix.
 * Handles state-driven cell styling (Green = Available, Yellow = Held, Red = Booked)
 * with sticky headers and responsive touch/scroll mechanics.
 */

import { MOCK_RESOURCES, MOCK_TIME_SLOTS } from '../mocks/mockData.js';

export class ResourceGrid {
    constructor(containerId, onSlotClick) {
        this.container = document.getElementById(containerId);
        this.onSlotClick = onSlotClick || (() => {});
        this.currentSlotsMap = new Map();
        this.currentUserId = null;
    }

    render(slotsData, currentUserId) {
        if (!this.container) return;
        this.currentUserId = currentUserId;

        // Index incoming slots for O(1) lookup
        this.currentSlotsMap.clear();
        slotsData.forEach(slot => {
            const key = `${slot.resource_name}__${slot.time_slot}`;
            this.currentSlotsMap.set(key, slot);
        });

        // Determine unique resources and time slots
        const resources = MOCK_RESOURCES;
        const timeSlots = MOCK_TIME_SLOTS;

        // Build HTML table/matrix
        let html = `
            <div class="matrix-table-wrapper">
                <table class="matrix-table" role="grid" aria-label="Resource Availability Matrix">
                    <thead>
                        <tr>
                            <th class="matrix-th-resource sticky-col">
                                <div class="th-resource-content">
                                    <span>Resources (${resources.length})</span>
                                </div>
                            </th>
                            ${timeSlots.map(time => `
                                <th class="matrix-th-time" scope="col">
                                    <div class="th-time-content">
                                        <span class="time-main">${time}</span>
                                        <span class="time-sub">60 min</span>
                                    </div>
                                </th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
        `;

        resources.forEach(res => {
            html += `
                <tr class="matrix-row" data-resource-name="${this.escapeHtml(res.name)}">
                    <th class="matrix-td-resource sticky-col" scope="row">
                        <div class="resource-card-mini">
                            <span class="res-icon">${res.icon || '📍'}</span>
                            <div class="res-meta">
                                <span class="res-title">${this.escapeHtml(res.name)}</span>
                                <span class="res-subtitle">${res.capacity} seats • ${res.type.toUpperCase()}</span>
                            </div>
                        </div>
                    </th>
            `;

            timeSlots.forEach(time => {
                const key = `${res.name}__${time}`;
                const slot = this.currentSlotsMap.get(key) || {
                    resource_name: res.name,
                    time_slot: time,
                    status: 'AVAILABLE'
                };

                const cellData = this.computeCellState(slot, currentUserId);

                html += `
                    <td class="matrix-td-slot">
                        <button type="button" 
                                class="slot-cell ${cellData.className}" 
                                data-resource="${this.escapeHtml(res.name)}"
                                data-slot="${time}"
                                data-slot-id="${slot.id || ''}"
                                data-status="${slot.status}"
                                aria-label="${this.escapeHtml(cellData.ariaLabel)}"
                                ${cellData.clickable ? '' : 'disabled'}
                        >
                            <div class="cell-inner">
                                <span class="cell-status-icon">${cellData.icon}</span>
                                <span class="cell-status-text">${cellData.badgeText}</span>
                                ${cellData.subText ? `<span class="cell-sub-text">${cellData.subText}</span>` : ''}
                            </div>
                            <div class="cell-tooltip">${this.escapeHtml(cellData.tooltip)}</div>
                        </button>
                    </td>
                `;
            });

            html += `</tr>`;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        this.container.innerHTML = html;
        this.attachClickEvents();
    }

    computeCellState(slot, currentUserId) {
        const isHeldByMe = slot.status === 'HELD' && slot.user_id === currentUserId;
        const isHeldByOther = slot.status === 'HELD' && slot.user_id !== currentUserId;
        const isBooked = slot.status === 'CONFIRMED';
        const isAvailable = slot.status === 'AVAILABLE';

        if (isBooked) {
            return {
                className: 'cell-booked',
                clickable: false,
                icon: '🔴',
                badgeText: 'Booked',
                subText: slot.agenda ? (slot.agenda.length > 14 ? slot.agenda.substring(0, 12) + '…' : slot.agenda) : (slot.user_id || 'Occupied'),
                tooltip: `Reserved by ${slot.user_id || 'User'}${slot.agenda ? `: "${slot.agenda}"` : ''}`,
                ariaLabel: `${slot.resource_name} at ${slot.time_slot} is booked.`
            };
        }

        if (isHeldByMe) {
            return {
                className: 'cell-held cell-held-me',
                clickable: true, // Allow clicking to resume/view modal
                icon: '⏳',
                badgeText: 'Held by You',
                subText: 'Click to Finalize',
                tooltip: 'You currently hold this slot (90s soft-lock). Click to finalize or cancel.',
                ariaLabel: `${slot.resource_name} at ${slot.time_slot} is held by you.`
            };
        }

        if (isHeldByOther) {
            return {
                className: 'cell-held cell-held-other',
                clickable: false,
                icon: '🔒',
                badgeText: 'Temporarily Held',
                subText: 'Soft-Locked (90s)',
                tooltip: 'Another user is currently finalizing this booking.',
                ariaLabel: `${slot.resource_name} at ${slot.time_slot} is held by another user.`
            };
        }

        // Available
        return {
            className: 'cell-available',
            clickable: true,
            icon: '🟢',
            badgeText: 'Available',
            subText: 'Select to Hold',
            tooltip: 'Click to place a 90-second temporary hold and reserve.',
            ariaLabel: `${slot.resource_name} at ${slot.time_slot} is available.`
        };
    }

    attachClickEvents() {
        const buttons = this.container.querySelectorAll('.slot-cell.cell-available, .slot-cell.cell-held-me');
        buttons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const resourceName = btn.dataset.resource;
                const timeSlot = btn.dataset.slot;
                const slotId = btn.dataset.slotId;
                const status = btn.dataset.status;

                const key = `${resourceName}__${timeSlot}`;
                const slot = this.currentSlotsMap.get(key) || {
                    id: slotId,
                    resource_name: resourceName,
                    time_slot: timeSlot,
                    status: status
                };

                this.onSlotClick(slot);
            });
        });
    }

    showLoading(isLoading) {
        if (!this.container) return;
        if (isLoading) {
            this.container.classList.add('grid-loading');
        } else {
            this.container.classList.remove('grid-loading');
        }
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
