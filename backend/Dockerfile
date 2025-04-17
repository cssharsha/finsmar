FROM python:3.10-slim

WORKDIR /app

# Install system dependencies if needed (e.g., for psycopg2)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port 5000 is the default for Flask
EXPOSE 5000

# Run Flask development server, accessible from outside the container
CMD ["flask", "run", "--host=0.0.0.0"]
