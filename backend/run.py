# backend/run.py
from app import create_app # Import the factory function from app.py

# Create the application instance using the factory
app = create_app()

# Optional: Add the block for direct execution (python run.py)
# Useful for some debugging scenarios, but 'flask run' is preferred.
if __name__ == '__main__':
    # Note: Debug mode should be controlled by FLASK_ENV=development
    app.run(host='0.0.0.0', port=5000)
