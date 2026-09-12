/**
 * timer.js
 * High-precision countdown timer synchronized with server/mock expires_at timestamp.
 * Prevents timer drift even if browser tab is backgrounded.
 */

export class HoldTimer {
    constructor() {
        this.intervalId = null;
        this.expiresAtMs = null;
        this.totalDurationSeconds = 90;
        this.onTick = null;
        this.onExpire = null;
    }

    /**
     * Starts countdown based on expiration timestamp or duration seconds.
     * @param {string|number} expiresAt - ISO timestamp string or seconds duration
     * @param {number} totalSeconds - Baseline duration (default 90)
     * @param {Function} onTick - Callback on every second tick
     * @param {Function} onExpire - Callback when time reaches 0
     */
    start(expiresAt, totalSeconds = 90, onTick = null, onExpire = null) {
        this.stop();

        this.totalDurationSeconds = totalSeconds;
        this.onTick = onTick;
        this.onExpire = onExpire;

        if (typeof expiresAt === 'string') {
            this.expiresAtMs = new Date(expiresAt).getTime();
        } else if (typeof expiresAt === 'number') {
            // Provided in seconds
            this.expiresAtMs = Date.now() + (expiresAt * 1000);
        } else {
            this.expiresAtMs = Date.now() + (totalSeconds * 1000);
        }

        // Run initial tick immediately
        this.tick();

        // Ticking loop
        this.intervalId = setInterval(() => {
            this.tick();
        }, 500);
    }

    tick() {
        const now = Date.now();
        const diffMs = this.expiresAtMs - now;
        const remainingSeconds = Math.max(0, Math.ceil(diffMs / 1000));
        const percent = Math.min(100, Math.max(0, (remainingSeconds / this.totalDurationSeconds) * 100));

        if (this.onTick) {
            this.onTick({
                remainingSeconds,
                totalSeconds: this.totalDurationSeconds,
                percent,
                formattedTime: this.formatTime(remainingSeconds),
                isUrgent: remainingSeconds <= 20
            });
        }

        if (remainingSeconds <= 0) {
            this.stop();
            if (this.onExpire) {
                this.onExpire();
            }
        }
    }

    stop() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    formatTime(totalSeconds) {
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }

    isActive() {
        return this.intervalId !== null;
    }
}
