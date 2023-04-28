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

**Build docker container**

(add sudo before command for synology)

```
$ docker-compose build
$ docker-compose up -d
```

To avoid problems with access rights to the file, you can change the UID and GID in both dockerfiles to match the desired user on the hosting server.

"-u" is UID & "-g" is GID.

```
RUN useradd -ms /bin/bash -u 1026 -g 100 user123
USER user123
```

To find the UID&GID of the host machine:

```
$ ID
```