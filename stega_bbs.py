#!/usr/bin/env python3
"""
steg_bbs.py — LSB PNG steganography with Blum Blum Shub XOR obfuscation.

Usage:
  python steg_bbs.py hide   <cover.png> <executable> <output.png> <seed>
  python steg_bbs.py reveal <steg.png>  <output_bin> <seed>

The seed is an integer; keep (p, q, seed) secret — that's your "key".
"""

import sys
import struct
import math
from PIL import Image


# ── Blum Blum Shub ────────────────────────────────────────────────────────────

# These must satisfy: p ≡ 3 (mod 4), q ≡ 3 (mod 4).
# M = p·q is the Blum integer. For real use, choose 512-bit+ primes.
# These 64-bit-ish primes are fine for demonstration.
P = 1000000007      # prime, 1000000007 % 4 == 3  ✓
Q = 999999937       # prime, 999999937  % 4 == 1  ✗ — see note below

# NOTE: 999999937 % 4 == 1, so let's use proper primes:
# p = 2147483647  (Mersenne prime M31, ≡ 3 mod 4)  ✓
# q = 2147483629  (prime, ≡ 1 mod 4)               ✗
# Let's pick two that actually satisfy the constraint:
#   p = 499979    499979 % 4 == 3  ✓
#   q = 500017    500017 % 4 == 1  ✗
# Finding valid pairs inline:

def find_blum_prime(start: int) -> int:
    """Find the next prime ≥ start that is ≡ 3 (mod 4)."""
    def is_prime(n: int) -> bool:
        if n < 2:
            return False
        if n % 2 == 0:
            return n == 2
        for i in range(3, int(math.isqrt(n)) + 1, 2):
            if n % i == 0:
                return False
        return True

    n = start | 1  # make odd
    while True:
        if is_prime(n) and n % 4 == 3:
            return n
        n += 2


# Default BBS parameters (override by passing your own p, q at construction).
DEFAULT_P = find_blum_prime(10**9 + 7)   # 1000000007  ← 1000000007 % 4 = 3 ✓
DEFAULT_Q = find_blum_prime(10**9 + 37)  # next Blum prime after that


class BlumBlumShub:
    """
    Blum Blum Shub CSPRNG.

    x_{n+1} = x_n^2 mod M
    Output bit = LSB(x_n)

    Security relies on the intractability of factoring M = p·q.
    The seed must be coprime to M (i.e. not divisible by p or q).
    """

    def __init__(self, seed: int, p: int = DEFAULT_P, q: int = DEFAULT_Q):
        assert p % 4 == 3, f"p must be ≡ 3 (mod 4), got {p % 4}"
        assert q % 4 == 3, f"q must be ≡ 3 (mod 4), got {q % 4}"
        self.M = p * q
        # Ensure seed is coprime to M
        if math.gcd(seed, self.M) != 1:
            raise ValueError("Seed shares a factor with M — choose a different seed.")
        self.x = (seed * seed) % self.M  # skip the raw seed, start at x_1

    def bit(self) -> int:
        """Generate one pseudorandom bit."""
        self.x = (self.x * self.x) % self.M
        return self.x & 1

    def byte(self) -> int:
        """Generate one pseudorandom byte (8 BBS iterations)."""
        b = 0
        for i in range(8):
            b = (b << 1) | self.bit()
        return b

    def keystream(self, length: int) -> bytes:
        """Generate `length` pseudorandom bytes."""
        return bytes(self.byte() for _ in range(length))


def xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(d ^ k for d, k in zip(data, key))


# ── LSB steganography ─────────────────────────────────────────────────────────

def capacity_bytes(img: Image.Image) -> int:
    """How many payload bytes fit in this image (3 bits/pixel via RGB LSBs)."""
    w, h = img.size
    total_bits = w * h * 3   # R, G, B — one bit each
    return total_bits // 8


def embed_bits(pixels: list, bit_iter) -> list:
    """
    Replace the LSB of each channel value with the next bit from bit_iter.
    pixels: flat list of (R, G, B) tuples (or RGBA — we touch only RGB).
    Returns a new flat list of tuples.
    """
    out = []
    for px in pixels:
        r, g, b = px[0], px[1], px[2]
        try:
            r = (r & 0xFE) | next(bit_iter)
            g = (g & 0xFE) | next(bit_iter)
            b = (b & 0xFE) | next(bit_iter)
        except StopIteration:
            # No more payload — leave remaining pixels untouched.
            out.append(px)
            continue
        out.append((r, g, b) + (px[3:] if len(px) > 3 else ()))
    return out


def bits_of(data: bytes):
    """Yield individual bits of a bytes object, MSB first."""
    for byte in data:
        for shift in range(7, -1, -1):
            yield (byte >> shift) & 1


def extract_bits(pixels: list, n_bits: int) -> bytes:
    """Read n_bits LSBs from the image channels; return as bytes (MSB first)."""
    bits = []
    for px in pixels:
        if len(bits) >= n_bits:
            break
        bits.append(px[0] & 1)
        if len(bits) >= n_bits:
            break
        bits.append(px[1] & 1)
        if len(bits) >= n_bits:
            break
        bits.append(px[2] & 1)

    # Pack bits into bytes
    result = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            chunk += [0] * (8 - len(chunk))
        b = 0
        for bit in chunk:
            b = (b << 1) | bit
        result.append(b)
    return bytes(result)


# ── High-level API ────────────────────────────────────────────────────────────

def hide(cover_path: str, exe_path: str, output_path: str, seed: int) -> None:
    """Embed an executable into a PNG using BBS-XOR + LSB steganography."""

    with open(exe_path, "rb") as f:
        payload = f.read()

    print(f"[*] Payload size : {len(payload):,} bytes")

    # XOR-obfuscate with BBS keystream
    bbs = BlumBlumShub(seed)
    keystream = bbs.keystream(len(payload))
    obfuscated = xor_bytes(payload, keystream)

    # Prepend a 4-byte big-endian length header (stored plaintext so we know
    # how many bits to read during extraction — not a secret).
    header = struct.pack(">I", len(payload))
    blob = header + obfuscated

    img = Image.open(cover_path).convert("RGB")
    cap = capacity_bytes(img)
    print(f"[*] Image capacity: {cap:,} bytes  ({cap - len(blob):,} bytes spare)")

    if len(blob) > cap:
        raise ValueError(
            f"Payload too large: need {len(blob)} bytes, image holds {cap}."
        )

    pixels = list(img.getdata())
    bit_src = iter(bits_of(blob))
    new_pixels = embed_bits(pixels, bit_src)

    out_img = Image.new("RGB", img.size)
    out_img.putdata(new_pixels)
    out_img.save(output_path, format="PNG")
    print(f"[+] Written to {output_path}")


def reveal(steg_path: str, output_path: str, seed: int) -> None:
    """Extract and de-obfuscate a hidden executable from a steganographic PNG."""

    img = Image.open(steg_path).convert("RGB")
    pixels = list(img.getdata())

    # Read the 4-byte length header first (32 bits)
    header_bytes = extract_bits(pixels, 32)
    payload_len = struct.unpack(">I", header_bytes)[0]
    print(f"[*] Payload length from header: {payload_len:,} bytes")

    # Now read the obfuscated payload
    total_bits_needed = 32 + payload_len * 8
    all_bytes = extract_bits(pixels, total_bits_needed)
    obfuscated = all_bytes[4:]  # skip the header we already read

    # XOR with same BBS keystream (same seed → same stream)
    bbs = BlumBlumShub(seed)
    keystream = bbs.keystream(payload_len)
    payload = xor_bytes(obfuscated, keystream)

    with open(output_path, "wb") as f:
        f.write(payload)

    # Restore executable bit
    import os, stat
    os.chmod(output_path, os.stat(output_path).st_mode | stat.S_IEXEC)

    print(f"[+] Extracted to {output_path}  ({payload_len:,} bytes, +x set)")


# ── CLI ───────────────────────────────────────────────────────────────────────

def usage():
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()

    mode = sys.argv[1]

    if mode == "hide" and len(sys.argv) == 6:
        _, _, cover, exe, output, seed_str = sys.argv
        hide(cover, exe, output, int(seed_str))

    elif mode == "reveal" and len(sys.argv) == 5:
        _, _, steg, output, seed_str = sys.argv
        reveal(steg, output, int(seed_str))

    else:
        usage()
