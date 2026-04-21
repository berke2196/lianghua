FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY asterdex_backend.py security.py config.py alerting.py db.py auth.py run.py ./

RUN mkdir -p data

EXPOSE 8000

CMD ["python", "run.py"]
