# stega-bbs

Modern malware analysis tools can often spot encrypted payloads by looking for structural or statistical clues, even if they cannot decrypt the data. For example, if an AES-encrypted block is simply added to the end of an image file, entropy scans can pick up the sudden change from normal image data to random-looking bytes. The stega_bbs.py tool takes a different approach. Instead of keeping the payload in one place, it spreads the hidden bits across the least significant bits of the image’s RGB channels. This removes obvious signs of extra data at the end of the file. As a result, simple detection methods that search for high-entropy areas or unusual file endings may not work. Still, this method does not make the hidden data blend in perfectly with natural image noise. The payload can still leave traces in the pixel data, especially if someone uses blind steganalysis to check local LSB patterns or how the data is spread out. This shows that keeping data secret with cryptography and hiding its presence with steganography are separate goals. A payload can stay unreadable even if someone can tell it is there. Sometimes, a weaker cryptographic method might avoid basic detection better than a stronger but more obvious encrypted block.


## Usage

```
python3 stega_bbs.py hide input.png /path/to/payload output.png 1337
python3 stega_bbs.py reveal output.png payload_revealed 1337
```

where `1337` is a '''random''' seed
