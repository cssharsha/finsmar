FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1 # Prevents python from writing pyc files
ENV PYTHONUNBUFFERED 1       # Prevents python from buffering stdout/stderr
ENV FLASK_ENV production      # Set Flask environment to production

WORKDIR /app

ENV PYTHONPATH /app

# Install system dependencies if needed (e.g., for psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port 5000 is the default for Flask
EXPOSE 5000

# Run the application using Gunicorn WSGI server
# Point Gunicorn to the Flask app instance created by the factory in run.py
# 'run:app' means look for variable 'app' in file 'run.py'
# --workers: Number of worker processes (adjust based on your CPU cores, start with 2-4)
# --bind: Listen on all interfaces within the container on port 5000
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:5000", "app:create_app()"]
