FROM python:3.12-slim

WORKDIR /app

COPY order_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY logger_config.py .
COPY order_service/app.py .
COPY order_service/repository.py .

CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5001", "app:app"]
