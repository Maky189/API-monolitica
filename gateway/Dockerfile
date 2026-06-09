FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY logger_config.py .
COPY gateway/app.py .

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
