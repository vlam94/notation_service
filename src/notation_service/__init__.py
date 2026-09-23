"""Converts a MusicXML score into a colinha."""

from flask import Flask

from notation_service.config import Config


def create_app(config: Config | None = None) -> Flask:
    """Build the Flask application."""
    # Imported here, not at the top: views pulls in music21, which the launcher never needs.
    from notation_service import views

    app = Flask(__name__)
    app.config["NOTATION"] = config or Config()
    app.register_blueprint(views.bp)
    return app
