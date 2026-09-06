FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libasound2-dev \
    libssl-dev \
    libsrtp2-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# بناء pjproject من المصدر (مطلوب لـ pjsua)
WORKDIR /tmp
RUN wget https://github.com/pjsip/pjproject/archive/refs/tags/2.13.tar.gz && \
    tar xzf 2.13.tar.gz && \
    cd pjproject-2.13 && \
    ./configure --disable-video --disable-sound --disable-opencore-amr --disable-oss --disable-alsa --disable-libyuv && \
    make dep && make && make install && \
    ldconfig

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
