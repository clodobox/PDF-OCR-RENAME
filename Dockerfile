FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get clean autoclean
RUN apt-get autoremove --yes
RUN apt -y update && apt -y upgrade
RUN apt -y install \
    ghostscript \
    ocrmypdf \
    python3 \
    python3-pdfminer \
    python3-pip \
    python3-poetry \
    python3-watchdog \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    pngquant \
    jbig2
RUN apt-get -y autoclean

COPY . /app

WORKDIR /app

# RUN which poetry
# RUN poetry --version

RUN poetry install

ENTRYPOINT ["poetry", "run", "python", "src/app.py"]