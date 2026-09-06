FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3 \
    python3-pip \
    python3-dev \
    libasound2-dev \
    libssl-dev \
    pkg-config \
    wget \
    swig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
RUN wget https://github.com/pjsip/pjproject/archive/refs/tags/2.13.tar.gz && \
    tar xzf 2.13.tar.gz && \
    cd pjproject-2.13 && \
    ./configure --disable-samples --disable-video --disable-sound --disable-oss --disable-alsa --disable-libyuv --disable-opencore-amr && \
    make dep && \
    make -j$(nproc) CFLAGS="-fPIC" CXXFLAGS="-fPIC" && \
    make install && \
    cd pjsip-apps/src/swig/python && \
    make CFLAGS="-fPIC" CXXFLAGS="-fPIC" && \
    make install && \
    ldconfig

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "app.py"]
