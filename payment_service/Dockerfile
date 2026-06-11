FROM python:3.12-slim

WORKDIR /app

COPY payment_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY logger_config.py .
COPY payment_service/app.py .

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5003", "app:app"]
