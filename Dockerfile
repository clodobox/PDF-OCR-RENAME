FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt-get clean autoclean && \
    apt-get autoremove --yes && \
    apt-get update && apt-get upgrade -y && \
    apt-get install -y \
    ghostscript \
    ocrmypdf \
    python3 \
    python3-venv \
    python3-dev \
    python3-pdfminer \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    pngquant \
    jbig2 && \
    apt-get autoclean -y && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv $VIRTUAL_ENV

RUN pip install --upgrade pip && \
    pip install pikepdf ocrmypdf pyyaml deskew watchdog

WORKDIR /app
COPY . /app

ENTRYPOINT ["python", "src/app.py"]
