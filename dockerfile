FROM alpine:latest
ENV PYTHONUNBUFFERED: "1"
ENV OCR_INPUT_DIRECTORY: "scan-input"
ENV OCR_OUTPUT_DIRECTORY: "ocr-output"
ENV OCR_OUTPUT_DIRECTORY_YEAR_MONTH: "0"
ENV OCR_ON_SUCCESS_ARCHIVE: "0"
ENV OCR_DESKEW: "1"
ENV OCR_ON_SUCCESS_DELETE: "1"
ENV OCR_JSON_SETTINGS: '{"rotate_pages": true, "skip_text": true, "language": "eng+fra", "output_type":"pdf"}'
ENV C_INCLUDE_PATH=$C_INCLUDE_PATH:/usr/include/freetype2
RUN apk add --update --no-cache python3 && ln -sf python3 /usr/bin/python
RUN apk add freetype-dev python3-dev py3-pybind11-dev qpdf-dev
RUN apk add tesseract-ocr tesseract-ocr-data-fra tesseract-ocr-data-deu ghostscript
RUN python3 -m ensurepip
RUN python3 -m venv venv
RUN apk add build-base
RUN pip3 install --no-cache --upgrade pip setuptools
RUN pip3 install wheel watchdog pdfminer.six pikepdf ocrmypdf
COPY run.sh run.sh
COPY RenameMyPDF.py RenameMyPDF.py
COPY watcher.py watcher.py
RUN ./run.sh