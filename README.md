# dexelpdf-v3
Docker volume
  scan-input
  ocr-output
  final-output

Build Alpine container
  docker build -t dexelpdfv3.0 -f dockerfile.alpine .

Build Ubuntu container
  docker build -t dexelpdfv3.0 -f dockerfile.ubuntu .