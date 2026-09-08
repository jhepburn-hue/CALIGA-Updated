import os
import warnings
from flask import Flask, render_template
from dotenv import load_dotenv

from routes.configs import configs_bp
from routes.testing import testing_bp
from routes.tools import tools_bp

# Suppress GCP authentication user warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.auth")

load_dotenv()


def create_app() -> Flask:
    """Creates and configures the main Flask application instance.

    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(__name__)
    app.config.from_prefixed_env()

    # Register application blueprints
    app.register_blueprint(configs_bp)
    app.register_blueprint(testing_bp)
    app.register_blueprint(tools_bp)

    @app.route("/")
    def index():
        """Renders the main application landing page.

        Returns:
            str: The rendered index HTML page template.
        """
        return render_template("index.html")

    return app


if __name__ == "__main__":
    app = create_app()
    app.secret_key = os.getenv("FLASK_SECRET_KEY")
    app.run(debug=True, port=5000)