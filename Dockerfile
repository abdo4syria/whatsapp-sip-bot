FROM python:3.8-slim-bullseye

RUN apt-get update && apt-get install -y --fix-missing \
    build-essential \
    python3-dev \
    libasound2-dev \
    libssl-dev \
    pkg-config \
    wget \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
