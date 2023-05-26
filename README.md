# dexelpdf-v3

This program was created for a business need: the electronic management of delivery notes.

Here is my usage:

> Scanner -> Scan2file(SMB) -> OCR -> detect string of text -> rename
> PDF with the string of text

You can edit RenameMyPDF.py to fit your needs.

Thanks to OCRmyPDF for their Watchdog which works very well.

This works on Synology x86-64 (with docker).
You just need to run the build commands below with "sudo".

Docker volume needed :

```
scan-input
ocr-output
final-output
```

---

### **Build docker container**

(add sudo before command for synology)

```
$ docker-compose build
$ docker-compose up -d
```

### Files permissions

To avoid problems with access permission to the file, you can change the UID and GID in **docker-compose.yml** to match the desired user on the hosting server.
