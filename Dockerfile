# Use a lightweight Python image
FROM python:3.10-slim

# Install system dependencies for MySQL
RUN apt-get update && apt-get install -y default-libmysqlclient-dev pkg-config gcc

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Collect static files (CSS/JS)
RUN python manage.py collectstatic --noinput

# Run the app using Gunicorn
# Replace 'myproject' with the name of your folder containing wsgi.py
# CORRECTED LAST LINE
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 missamma_backend.wsgi:application