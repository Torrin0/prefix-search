FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY load_catalog.py .
COPY search_service.py .
COPY evaluate.py .
COPY utils.py .

RUN mkdir -p /app/data /app/logs

EXPOSE 5000

CMD ["python", "search_service.py"]
