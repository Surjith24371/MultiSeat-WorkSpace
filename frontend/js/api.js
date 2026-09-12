/**
 * api.js
 * Centralized API Communication Service.
 * Connects to live Flask backend endpoints or seamlessly delegates
 * to the stateful Mock Service when running in offline/standalone mode.
 */

import { mockBackend } from '../mocks/mockService.js';

class ApiService {
    constructor() {
        // Toggle for mock vs live API
        this.useMocks = true;
        this.baseUrl = ''; // relative to current origin, or http://localhost:5000
    }

    setMockMode(enableMock) {
        this.useMocks = Boolean(enableMock);
        console.info(`[API] Switched mode: ${this.useMocks ? 'SIMULATED (Offline Mock)' : 'LIVE (Flask Backend)'}`);
    }

    isMock() {
        return this.useMocks;
    }

    /**
     * GET /api/resources/availability?date=YYYY-MM-DD
     */
    async getAvailability(date, currentUserId) {
        if (this.useMocks) {
            // Small synthetic delay for realism (120ms)
            await new Promise(r => setTimeout(r, 120));
            return mockBackend.getAvailability(date, currentUserId);
        }

        try {
            const url = `${this.baseUrl}/api/resources/availability?date=${encodeURIComponent(date)}&user_id=${encodeURIComponent(currentUserId || '')}`;
            const res = await fetch(url, {
                headers: { 'Accept': 'application/json' }
            });
            const data = await res.json().catch(() => ({}));
            return {
                status: res.status,
                data: data,
                ok: res.ok
            };
        } catch (err) {
            console.error('[API] Network error fetching availability:', err);
            return {
                status: 0,
                data: { error: 'NETWORK_ERROR', message: 'Unable to connect to backend server. Is Flask running?' },
                ok: false
            };
        }
    }

    /**
     * POST /api/resources/hold
     */
    async placeHold(resourceName, date, timeSlot, userId) {
        if (this.useMocks) {
            await new Promise(r => setTimeout(r, 150));
            return mockBackend.placeHold(resourceName, date, timeSlot, userId);
        }

        try {
            const url = `${this.baseUrl}/api/resources/hold`;
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    resource_name: resourceName,
                    date: date,
                    time_slot: timeSlot,
                    user_id: userId
                })
            });
            const data = await res.json().catch(() => ({}));
            return {
                status: res.status,
                data: data,
                ok: res.ok
            };
        } catch (err) {
            console.error('[API] Network error placing hold:', err);
            return {
                status: 0,
                data: { error: 'NETWORK_ERROR', message: 'Could not connect to server to place hold.' },
                ok: false
            };
        }
    }

    /**
     * POST /api/resources/confirm
     */
    async confirmBooking(slotId, userId, agenda, collaborators) {
        if (this.useMocks) {
            await new Promise(r => setTimeout(r, 180));
            return mockBackend.confirmBooking(slotId, userId, agenda, collaborators);
        }

        try {
            const url = `${this.baseUrl}/api/resources/confirm`;
            const res = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({
                    slot_id: slotId,
                    user_id: userId,
                    agenda: agenda,
                    collaborators: collaborators
                })
            });
            const data = await res.json().catch(() => ({}));
            return {
                status: res.status,
                data: data,
                ok: res.ok
            };
        } catch (err) {
            console.error('[API] Network error confirming booking:', err);
            return {
                status: 0,
                data: { error: 'NETWORK_ERROR', message: 'Could not connect to server to confirm booking.' },
                ok: false
            };
        }
    }

    /**
     * DELETE /api/resources/cancel/{id}
     */
    async cancelSlot(slotId, userId) {
        if (this.useMocks) {
            await new Promise(r => setTimeout(r, 100));
            return mockBackend.cancelSlot(slotId, userId);
        }

        try {
            const url = `${this.baseUrl}/api/resources/cancel/${encodeURIComponent(slotId)}`;
            const res = await fetch(url, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ user_id: userId })
            });
            const data = await res.json().catch(() => ({}));
            return {
                status: res.status,
                data: data,
                ok: res.ok
            };
        } catch (err) {
            console.error('[API] Network error cancelling slot:', err);
            return {
                status: 0,
                data: { error: 'NETWORK_ERROR', message: 'Could not connect to server to cancel hold.' },
                ok: false
            };
        }
    }
}

export const API = new ApiService();
