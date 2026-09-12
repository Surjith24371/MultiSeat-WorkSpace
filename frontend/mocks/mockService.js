/**
 * mockService.js
 * In-memory stateful mock engine simulating the Flask + Supabase backend.
 * Accurately implements 90s soft-locks, 3h daily quotas, atomic status changes,
 * and standard HTTP status codes (200, 201, 409, 410, 422).
 */

import { MOCK_RESOURCES, MOCK_TIME_SLOTS } from './mockData.js';

class MockBackendEngine {
    constructor() {
        this.slots = new Map();
        this.HOLD_DURATION_SECONDS = 90;
        this.MAX_DAILY_HOURS = 3;
        this.initializeDefaultData();
    }

    getKey(resourceName, date, timeSlot) {
        return `${resourceName}__${date}__${timeSlot}`;
    }

    /**
     * Initializes initial sample matrix with a realistic mix of Available, Held, and Booked slots.
     */
    initializeDefaultData() {
        const today = new Date().toISOString().split('T')[0];

        MOCK_RESOURCES.forEach((resource, rIdx) => {
            MOCK_TIME_SLOTS.forEach((slot, sIdx) => {
                const key = this.getKey(resource.name, today, slot);
                let status = 'AVAILABLE';
                let userId = null;
                let holdExpiresAt = null;
                let agenda = null;
                let collaborators = [];

                // Seed some realistic existing bookings and holds
                if (rIdx === 0 && sIdx === 1) {
                    // Apex Boardroom @ 10:00 - Booked by Alice
                    status = 'CONFIRMED';
                    userId = 'user_alice';
                    agenda = 'Q3 AI Strategy & Compute Allocation';
                    collaborators = ['bob@workspace.io', 'charlie@workspace.io'];
                } else if (rIdx === 1 && sIdx === 2) {
                    // Zenith @ 11:00 - Booked by Charlie
                    status = 'CONFIRMED';
                    userId = 'user_charlie';
                    agenda = 'Product Roadmapping & UI Review';
                    collaborators = ['team@workspace.io'];
                } else if (rIdx === 2 && sIdx === 0) {
                    // Nexus @ 09:00 - Booked by Charlie
                    status = 'CONFIRMED';
                    userId = 'user_charlie';
                    agenda = 'Daily Standup Sync';
                } else if (rIdx === 4 && sIdx === 3) {
                    // Pod 101 @ 12:00 - Held by Bob with 60s remaining
                    status = 'HELD';
                    userId = 'user_bob';
                    holdExpiresAt = new Date(Date.now() + 60 * 1000).toISOString();
                }

                this.slots.set(key, {
                    id: `slot_${rIdx + 1}_${sIdx + 1}`,
                    resource_name: resource.name,
                    resource_type: resource.type,
                    capacity: resource.capacity,
                    icon: resource.icon,
                    booking_date: today,
                    time_slot: slot,
                    status: status,
                    user_id: userId,
                    hold_expires_at: holdExpiresAt,
                    agenda: agenda,
                    collaborators: collaborators,
                    updated_at: new Date().toISOString()
                });
            });
        });
    }

    /**
     * Lazy check: if a slot is HELD and its hold_expires_at is in the past,
     * it automatically decays to AVAILABLE.
     */
    decayExpiredHolds() {
        const now = Date.now();
        for (const [key, slot] of this.slots.entries()) {
            if (slot.status === 'HELD' && slot.hold_expires_at) {
                const expiresTime = new Date(slot.hold_expires_at).getTime();
                if (expiresTime <= now) {
                    slot.status = 'AVAILABLE';
                    slot.user_id = null;
                    slot.hold_expires_at = null;
                    slot.agenda = null;
                    slot.collaborators = [];
                    slot.updated_at = new Date().toISOString();
                }
            }
        }
    }

    /**
     * Calculates user cumulative hours for a given date.
     * Counts CONFIRMED + currently active HELD slots.
     */
    getUserActiveHours(userId, date) {
        this.decayExpiredHolds();
        let hours = 0;
        for (const slot of this.slots.values()) {
            if (slot.booking_date === date && slot.user_id === userId) {
                if (slot.status === 'CONFIRMED' || slot.status === 'HELD') {
                    hours += 1;
                }
            }
        }
        return hours;
    }

    /**
     * GET /api/resources/availability?date=YYYY-MM-DD
     */
    getAvailability(date, currentUserId) {
        this.decayExpiredHolds();
        const dateSlots = [];

        for (const slot of this.slots.values()) {
            if (slot.booking_date === date) {
                dateSlots.push({ ...slot });
            }
        }

        // If date has no slots yet, generate clean available grid for that date
        if (dateSlots.length === 0) {
            MOCK_RESOURCES.forEach((resource, rIdx) => {
                MOCK_TIME_SLOTS.forEach((slot, sIdx) => {
                    const key = this.getKey(resource.name, date, slot);
                    const newSlot = {
                        id: `slot_${date}_${rIdx + 1}_${sIdx + 1}`,
                        resource_name: resource.name,
                        resource_type: resource.type,
                        capacity: resource.capacity,
                        icon: resource.icon,
                        booking_date: date,
                        time_slot: slot,
                        status: 'AVAILABLE',
                        user_id: null,
                        hold_expires_at: null,
                        agenda: null,
                        collaborators: [],
                        updated_at: new Date().toISOString()
                    };
                    this.slots.set(key, newSlot);
                    dateSlots.push({ ...newSlot });
                });
            });
        }

        const userHours = currentUserId ? this.getUserActiveHours(currentUserId, date) : 0;

        return {
            status: 200,
            data: {
                date: date,
                slots: dateSlots,
                quota: {
                    user_id: currentUserId,
                    used_hours: userHours,
                    max_hours: this.MAX_DAILY_HOURS,
                    remaining_hours: Math.max(0, this.MAX_DAILY_HOURS - userHours)
                }
            }
        };
    }

    /**
     * POST /api/resources/hold
     * Places 90s soft-lock with quota validation.
     */
    placeHold(resourceName, date, timeSlot, userId) {
        this.decayExpiredHolds();

        // 1. Quota Check
        const currentHours = this.getUserActiveHours(userId, date);
        if (currentHours >= this.MAX_DAILY_HOURS) {
            return {
                status: 422,
                data: {
                    error: 'QUOTA_EXCEEDED',
                    message: `Daily booking quota exceeded! You have already claimed ${currentHours}/${this.MAX_DAILY_HOURS} hours for ${date}.`
                }
            };
        }

        // 2. Concurrency / Availability Check
        const key = this.getKey(resourceName, date, timeSlot);
        const slot = this.slots.get(key);

        if (!slot || slot.status === 'CONFIRMED' || (slot.status === 'HELD' && slot.user_id !== userId)) {
            return {
                status: 409,
                data: {
                    error: 'SLOT_TAKEN',
                    message: 'Conflict: This slot is already held or booked by another user.'
                }
            };
        }

        // 3. Apply Hold
        const expiresAt = new Date(Date.now() + this.HOLD_DURATION_SECONDS * 1000).toISOString();
        slot.status = 'HELD';
        slot.user_id = userId;
        slot.hold_expires_at = expiresAt;
        slot.updated_at = new Date().toISOString();

        return {
            status: 201,
            data: {
                success: true,
                slot_id: slot.id,
                resource_name: slot.resource_name,
                booking_date: slot.booking_date,
                time_slot: slot.time_slot,
                expires_at: expiresAt,
                expires_in_seconds: this.HOLD_DURATION_SECONDS,
                message: 'Slot held successfully. You have 90 seconds to finalize your reservation.'
            }
        };
    }

    /**
     * POST /api/resources/confirm
     * Finalizes booking.
     */
    confirmBooking(slotId, userId, agenda, collaborators) {
        this.decayExpiredHolds();

        let targetSlot = null;
        for (const slot of this.slots.values()) {
            if (slot.id === slotId) {
                targetSlot = slot;
                break;
            }
        }

        if (!targetSlot) {
            return {
                status: 404,
                data: { error: 'NOT_FOUND', message: 'Target slot not found.' }
            };
        }

        // Check hold validity
        if (targetSlot.status !== 'HELD' || targetSlot.user_id !== userId) {
            return {
                status: 410,
                data: {
                    error: 'HOLD_EXPIRED',
                    message: 'Your hold has expired or was claimed by another session.'
                }
            };
        }

        const now = Date.now();
        const expiresTime = new Date(targetSlot.hold_expires_at).getTime();
        if (expiresTime <= now) {
            targetSlot.status = 'AVAILABLE';
            targetSlot.user_id = null;
            targetSlot.hold_expires_at = null;
            return {
                status: 410,
                data: {
                    error: 'HOLD_EXPIRED',
                    message: 'Your 90-second hold expired right before confirmation.'
                }
            };
        }

        // Confirm
        targetSlot.status = 'CONFIRMED';
        targetSlot.hold_expires_at = null;
        targetSlot.agenda = agenda || 'Collaborative Session';
        targetSlot.collaborators = Array.isArray(collaborators) ? collaborators : [];
        targetSlot.updated_at = new Date().toISOString();

        return {
            status: 200,
            data: {
                success: true,
                slot: { ...targetSlot },
                message: 'Reservation confirmed successfully!'
            }
        };
    }

    /**
     * DELETE /api/resources/cancel/{id}
     */
    cancelSlot(slotId, userId) {
        let targetSlot = null;
        for (const slot of this.slots.values()) {
            if (slot.id === slotId) {
                targetSlot = slot;
                break;
            }
        }

        if (!targetSlot) {
            return {
                status: 404,
                data: { error: 'NOT_FOUND', message: 'Reservation slot not found.' }
            };
        }

        // Only owner can cancel
        if (targetSlot.user_id && targetSlot.user_id !== userId) {
            return {
                status: 403,
                data: { error: 'FORBIDDEN', message: 'You do not own this reservation.' }
            };
        }

        targetSlot.status = 'AVAILABLE';
        targetSlot.user_id = null;
        targetSlot.hold_expires_at = null;
        targetSlot.agenda = null;
        targetSlot.collaborators = [];
        targetSlot.updated_at = new Date().toISOString();

        return {
            status: 200,
            data: {
                success: true,
                message: 'Reservation slot released successfully.'
            }
        };
    }
}

export const mockBackend = new MockBackendEngine();
