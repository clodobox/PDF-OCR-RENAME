#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pikepdf
import ocrmypdf
from pdfminer.high_level import extract_text
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
import yaml

with open('./config.yml', 'r') as file:
    config = yaml.safe_load(file)

INPUT_DIRECTORY = config['input_directory']
OUTPUT_DIRECTORY = config['output_directory']
BACKUP_DIRECTORY = config['backup_directory']
ON_SUCCESS_DELETE = config['on_success_delete']
DESKEW = config['deskew']
OCR_JSON_SETTINGS = config['ocr_json_settings']
POLL_NEW_FILE_SECONDS = config['poll_new_file_seconds']
USE_POLLING = config['use_polling']
RETRIES_LOADING_FILE = config['retries_loading_file']
LOGLEVEL = config['loglevel']
PATTERNS = config['patterns']

# pylint: disable=logging-format-interpolation

log = logging.getLogger('ocrmypdf-watcher')

def wait_for_file_ready(file_path):
    retries = RETRIES_LOADING_FILE
    while retries:
        try:
            pdf = pikepdf.open(file_path)
        except (FileNotFoundError, pikepdf.PdfError) as e:
            log.info(f"[watcher] File {file_path} is not ready yet")
            log.debug("[watcher] Exception was", exc_info=e)
            time.sleep(POLL_NEW_FILE_SECONDS)
            retries -= 1
        else:
            pdf.close()
            return True
    return False

def execute_ocrmypdf(file_path):
    file_path = Path(file_path)
    output_path = Path(OUTPUT_DIRECTORY) / file_path.name

    log.info("[watcher] " + "-" * 20)
    log.info(f'[watcher] New file: {file_path}. Waiting until fully loaded...')
    if not wait_for_file_ready(file_path):
        log.info(f"[watcher] Gave up waiting for {file_path} to become ready")
        return
    log.info(f'[watcher] Attempting to OCRmyPDF to: {output_path}')

    if BACKUP_DIRECTORY:
        backup_path = Path(BACKUP_DIRECTORY) / file_path.name
        log.info(f'[watcher] Backing up file to: {backup_path}')
        shutil.copy2(file_path, backup_path)

    exit_code = ocrmypdf.ocr(
        input_file=file_path,
        output_file=output_path, 
        deskew=DESKEW,
        force_ocr=True,
        **OCR_JSON_SETTINGS,
    )
    if exit_code == 0:
        if ON_SUCCESS_DELETE:
            log.info(f'[watcher] OCR is done. Deleting: {file_path}')
            file_path.unlink()
        else:
            log.info('[watcher] OCR is done')
        
        process_pdf(output_path)
    else:
        log.info('[watcher] OCR is done')

def autocorrect_match(match):
    match = match.replace(" ", "")

    if match.startswith('P0-'):
        match = 'PO' + match[2:]
    elif match.startswith('PQ-'):
        match = 'PO' + match[2:]
    elif match.startswith('RNW-'):
        match = 'RNWS' + match[3:]
    elif match.startswith('5P0-'):
        match = 'SPO' + match[3:]
    elif match.startswith('56R-'):
        match = 'SGR' + match[3:]

    parts = re.match(r'([A-Z]+)[-]?(\d{1,2})[-]?(\d{1,4})', match)

    if parts is not None:
        prefix = parts.group(1)
        second_part = parts.group(2).zfill(2)
        last_part = parts.group(3).zfill(4)

        second_part = second_part.replace("O", "0").replace("I", "1").replace("S", "5").replace("B", "8").replace("Z", "2").replace("G", "6")
        last_part = last_part.replace("O", "0").replace("I", "1").replace("S", "5").replace("B", "8").replace("Z", "2").replace("G", "6")

        if prefix in ["PO", "SPO", "RNWS", "SGR", "SSR"]:
            second_part = "2" + second_part[1:]

        corrected = f"{prefix}-{second_part}-{last_part}"
        return corrected
    else:
        return match

def process_pdf(path):
    path_str = str(path)
    if path_str.endswith('.pdf'):
        print(f'[renamer] Processing file: {path_str}')

        try:
            text = extract_text(path_str)
            matches = re.findall(r'(?:P0|PO|SPO|RNWS|SGR|SSR) ?\d?-?\d{1,2}-\d{1,4}', text, re.IGNORECASE)
            matches = [match.upper() for match in matches]

            if matches:
                matches = [autocorrect_match(match) for match in matches]
                matches = list(set(matches))
                matches.sort()
            final_name = '_'.join(matches) + '.pdf'
            max_length = 150 - 4
            if len(final_name) > max_length:
                final_name = final_name[:max_length] + '.pdf'

            if os.path.exists(os.path.join(OUTPUT_DIRECTORY, final_name)):
                num = 1
                while os.path.exists(os.path.join(OUTPUT_DIRECTORY, final_name[:-4] + f'({num}).pdf')):
                    num += 1
                final_name = final_name[:-4] + f'({num}).pdf'
            os.rename(path_str, os.path.join(os.path.dirname(path_str), final_name))
            print(f'[renamer] Processed file: {final_name}')
        except Exception as e:
            print(f'[renamer] Error processing file: {path_str}. Error: {e}')
            if os.path.exists(path_str):
                if not os.path.exists('ERROR'):
                    os.mkdir('ERROR')
                shutil.move(path_str, os.path.join('ERROR', os.path.basename(path_str)))
                print(f'[renamer] Moved file with error to ERROR folder: {path_str}')

class HandleObserverEvent(PatternMatchingEventHandler):
    def on_any_event(self, event):
        if event.event_type in ['created']:
            execute_ocrmypdf(event.src_path)

def ensure_directory_exists(directory):
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        log.info(f'[watcher] Created directory: {directory}')

def main():
    ocrmypdf.configure_logging(
        verbosity=(
            ocrmypdf.Verbosity.default
            if LOGLEVEL != 'DEBUG'
            else ocrmypdf.Verbosity.debug
        ),
        manage_root_logger=True,
    )
    log.setLevel(LOGLEVEL)
    log.info(
        f"[watcher] Starting OCRmyPDF watcher with config:\n"
        f"Input Directory: {INPUT_DIRECTORY}\n"
        f"Output Directory: {OUTPUT_DIRECTORY}\n"
    )
    log.debug(
        f"[watcher] INPUT_DIRECTORY: {INPUT_DIRECTORY}\n"
        f"OUTPUT_DIRECTORY: {OUTPUT_DIRECTORY}\n"
        f"ON_SUCCESS_DELETE: {ON_SUCCESS_DELETE}\n"
        f"DESKEW: {DESKEW}\n"
        f"ARGS: {OCR_JSON_SETTINGS}\n"
        f"POLL_NEW_FILE_SECONDS: {POLL_NEW_FILE_SECONDS}\n"
        f"RETRIES_LOADING_FILE: {RETRIES_LOADING_FILE}\n"
        f"USE_POLLING: {USE_POLLING}\n"
        f"LOGLEVEL: {LOGLEVEL}"
    )
    if 'input_file' in OCR_JSON_SETTINGS or 'output_file' in OCR_JSON_SETTINGS:
        log.error('[watcher] OCR_JSON_SETTINGS should not specify input file or output file')
        sys.exit(1)
    
    ensure_directory_exists(INPUT_DIRECTORY)
    ensure_directory_exists(OUTPUT_DIRECTORY)
    ensure_directory_exists(BACKUP_DIRECTORY)
    
    handler = HandleObserverEvent(patterns=PATTERNS)
    
    if USE_POLLING:
        observer = PollingObserver()
    else:
        observer = Observer()
    observer.schedule(handler, INPUT_DIRECTORY, recursive=True)
    observer.start()
    print(f'[watcher] Watching folder: {INPUT_DIRECTORY}')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()