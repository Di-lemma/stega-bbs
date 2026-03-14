# stega-bbs

Modern **malware analysis** tools detect encrypted payloads not by decrypting them, but by **identifying their presence**. For example, a contiguous AES-encrypted segment appended to an image file can be detected through entropy analysis. Tools such as binwalk -E show a sharp transition from typical image data to **near-perfect randomness**, providing a clear indicator without requiring cryptanalysis. In contrast, stega_bbs.py uses a different strategy: it conceals the existence of a payload rather than its content. By distributing payload bits across the least significant bits of the cover image's RGB channels and further obfuscating them with a **Blum Blum Shub keystream**, the ciphertext is rendered non-contiguous and spatially dispersed throughout the image, making it statistically indistinguishable from natural pixel noise. As a result, there is no abrupt entropy change, no distinctive byte signature, and no identifiable segment following the IEND marker. This demonstrates that **cryptographic robustness and steganographic concealment are independent properties**. Most malware developers prioritize the former while neglecting the latter. In some cases, a less sophisticated tool may prove more effective.

## Usage

```
python3 stega_bbs.py hide input.png /path/to/payload output.png 1337
python3 stega_bbs.py reveal output.png payload_revealed 1337
```

where `1337` is a '''random''' seed
