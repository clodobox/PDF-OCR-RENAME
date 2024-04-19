# PDF-OCR-RENAME

This program was created for a business need: the electronic management of delivery notes.

Here is my usage:

> Scanner -> Scan2file(SMB) -> OCR -> detect string of text -> rename
> PDF with the string of text

You can edit RenameMyPDF.py to fit your needs.

Thanks to OCRmyPDF for their Watchdog which works very well.
The watcher.py you'll find in this project is modified to preserve the original timestamp of the processed file.

This works on Synology x86-64 (with docker).
You just need to run the build commands below with "sudo" or use "Project" in Container Manager (DSM7.2+)

## What does it do?

1. Search for new files in "scan-input".
2. watcher.py perform OCR on this file, rotate PDF pages if necessary
3. move the file with OCR to the "ocr-output" folder
4. RenameMyPDF.py scan ocr-output folder for new files
5. finds a text string in the PDF
6. Autocorrect this text string and rename the PDF with
7. Moves file to final-output

## Build docker container

This version allows you to mount either NFS or local shares for input/output folders.
You can choose what suits you best in docker-compose.yaml

Docker volume needed :

```
scan-input
ocr-output
final-output
```

(add sudo before command for synology)

```
docker-compose build
docker-compose up -d
```

## Information

* This is an unfinished project that will certainly never be completed.
  No notion of safety, optimization or simply common sense was used
* This project is used in a very specific context and will certainly not be usable out-of-the-box by anyone.

* If you'd like to adapt it for your own use to recognize other text elements in PDFs, feel free to use AI to easily find the changes you need to make to the RenameMyPDF.py file.
* CPU requirements can be very high if you're processing a lot of files. It is possible to limit the number of threads in the OCR module.

## Next step

* Bug fix with RenameMyPDF (file not found)
* Group all parameters together so that anything useful can be changed quickly.
* Making a version in a single docker
* Improved logging
