FROM python:3.8-slim
RUN apt-get update && apt-get install -y \
    build-essential libasound2-dev libssl-dev libsrtp2-dev \
    libavcodec-dev libavformat-dev libswscale-dev libv4l-dev wget \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "app.py"]
