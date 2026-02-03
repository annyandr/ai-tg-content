"""Flask application entry point"""
from flask import Flask
from flask_cors import CORS
from config import Config


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enable CORS
    CORS(app)

    # Register blueprints
    from app.routes import dashboard, posts, channels

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(posts.bp)
    app.register_blueprint(channels.bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=3000,
        debug=app.config['DEBUG']
    )
