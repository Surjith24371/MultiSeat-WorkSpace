from flask import Flask, jsonify
from flask_cors import CORS
from config import FLASK_PORT, FLASK_ENV
from routes import resources_bp

def create_app():
    """
    Application factory pattern to create and configure the Flask app.
    """
    app = Flask(__name__)

    # Enable Cross-Origin Resource Sharing (CORS)
    # This allows Member 3's frontend (running on different port/domain) to call our backend API
    CORS(app)

    # Register Blueprints
    app.register_blueprint(resources_bp)

    # ------------------------------------------------------------------------
    # Root Welcome Endpoint & Health Check
    # ------------------------------------------------------------------------
    @app.route("/", methods=["GET"])
    def root():
        """
        Root endpoint providing an API overview and available endpoints.
        """
        return jsonify({
            "success": True,
            "message": "MultiSeat-WorkSpace Backend API is running",
            "version": "1.0.0",
            "endpoints": {
                "health": "GET /api/health",
                "resources_status": "GET /api/resources/status",
                "availability": "GET /api/resources/availability?date=YYYY-MM-DD",
                "hold": "POST /api/resources/hold",
                "confirm": "POST /api/resources/confirm",
                "cancel": "DELETE /api/resources/cancel/<slot_id>"
            }
        }), 200

    @app.route("/api/health", methods=["GET"])
    def health_check():
        """
        Simple health check endpoint to verify backend connectivity.
        Returns:
            JSON object confirming backend is running with HTTP 200 OK.
        """
        return jsonify({
            "success": True,
            "message": "Backend is running"
        }), 200
        

    # ------------------------------------------------------------------------
    # Error Handlers (Return clean JSON rather than default HTML pages)
    # ------------------------------------------------------------------------
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "success": False,
            "error": "Resource not found",
            "message": str(error)
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "success": False,
            "error": "Internal server error",
            "message": "An unexpected error occurred on the server."
        }), 500

    return app


# Create the application instance
app = create_app()

if __name__ == "__main__":
    print(f"Starting MultiSeat-WorkSpace Backend on port {FLASK_PORT} ({FLASK_ENV} mode)...")
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=(FLASK_ENV == "development"))
