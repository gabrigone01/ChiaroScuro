#!/usr/bin/env python3
"""Icona di Chiaroscuro disegnata in puro Python (nessuna libreria): tre fasci di luce colorati sopra una tastiera,
su un quadrato arrotondato color castagna. Scrive PNG, ICO (Windows) e, su macOS, ICNS (con iconutil).

    python3 icon.py OUT_DIR        -> OUT_DIR/icon.png (1024), icon.ico, icon.icns (solo macOS)
"""
import math, os, shutil, struct, subprocess, sys, tempfile, zlib


def png_bytes(w, h, rgba):
    raw = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
            chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def draw(S=512):
    """Disegna l'icona a S x S (RGBA, lista piatta)."""
    px = bytearray(S * S * 4)
    rad = S * 0.22                       # raggio degli angoli
    beams = [(0.24, (255, 140, 40)), (0.50, (230, 60, 150)), (0.76, (80, 150, 255))]
    key_top, key_bot = S * 0.70, S * 0.90
    for y in range(S):
        for x in range(S):
            # quadrato arrotondato (con bordo morbido)
            dx = max(rad - x - 0.5, 0, x + 0.5 - (S - rad))
            dy = max(rad - y - 0.5, 0, y + 0.5 - (S - rad))
            d = math.hypot(dx, dy) - rad
            a = max(0.0, min(1.0, 0.5 - d))
            if a <= 0:
                continue
            fy = y / S
            # sfondo: castagna più chiaro in basso
            r, g, b = 28 + 22 * fy, 16 + 12 * fy, 9 + 6 * fy
            # fasci di luce dal basso (sotto la tastiera) verso l'alto, additivi
            for bx, (cr, cg, cb) in beams:
                if y < key_top:
                    h = (key_top - y) / key_top                     # 0 in basso, 1 in alto
                    width = S * (0.035 + 0.16 * h)
                    off = abs(x - S * bx) / width
                    k = max(0.0, 1 - off) ** 1.6 * (1 - 0.55 * h) * 0.95
                    r, g, b = r + cr * k, g + cg * k, b + cb * k
            # tastiera
            if key_top <= y <= key_bot and S * 0.10 <= x <= S * 0.90:
                kx = (x - S * 0.10) / (S * 0.80) * 7            # 7 tasti bianchi
                wi, fr = int(kx), kx - int(kx)
                r, g, b = (240, 233, 222) if 0.06 < fr < 0.94 else (60, 50, 44)
                if y < key_top + (key_bot - key_top) * 0.6 and wi in (0, 1, 3, 4, 5) and fr > 0.68:
                    r, g, b = 20, 16, 14                           # tasti neri
                if y < key_top + (key_bot - key_top) * 0.6 and wi in (1, 2, 4, 5, 6) and fr < 0.32:
                    r, g, b = 20, 16, 14
            i = (y * S + x) * 4
            px[i:i + 4] = bytes((int(min(255, r)), int(min(255, g)), int(min(255, b)), int(a * 255)))
    return px


def downscale(px, S, n):
    """Riduce S x S -> n x n con media dei pixel (premoltiplicata per l'alfa)."""
    f = S // n
    out = bytearray(n * n * 4)
    for y in range(n):
        for x in range(n):
            acc = [0, 0, 0, 0]
            for yy in range(y * f, y * f + f):
                base = (yy * S + x * f) * 4
                for xx in range(f):
                    j = base + xx * 4
                    al = px[j + 3]
                    acc[0] += px[j] * al; acc[1] += px[j + 1] * al; acc[2] += px[j + 2] * al; acc[3] += al
            cnt = f * f
            al = acc[3] / cnt
            i = (y * n + x) * 4
            if acc[3]:
                out[i:i + 4] = bytes((int(acc[0] / acc[3]), int(acc[1] / acc[3]), int(acc[2] / acc[3]), int(al)))
    return out


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    S = 1024
    big = draw(S)
    sizes = [16, 32, 48, 64, 128, 256, 512]
    imgs = {S: big}
    for n in sizes:
        imgs[n] = downscale(big, S, n)
    with open(os.path.join(out_dir, "icon.png"), "wb") as fh:
        fh.write(png_bytes(512, 512, imgs[512]))
    # ICO con immagini PNG (Windows Vista e successivi)
    ico = [16, 32, 48, 64, 128, 256]
    data = [png_bytes(n, n, imgs[n]) for n in ico]
    head = struct.pack("<HHH", 0, 1, len(ico))
    offset = 6 + 16 * len(ico)
    entries = b""
    for n, d in zip(ico, data):
        entries += struct.pack("<BBBBHHII", n % 256, n % 256, 0, 0, 1, 32, len(d), offset)
        offset += len(d)
    with open(os.path.join(out_dir, "icon.ico"), "wb") as fh:
        fh.write(head + entries + b"".join(data))
    # ICNS (macOS) con iconutil
    if sys.platform == "darwin" and shutil.which("iconutil"):
        tmp = tempfile.mkdtemp()
        iconset = os.path.join(tmp, "icon.iconset")
        os.makedirs(iconset)
        for n in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                m = n * scale
                with open(os.path.join(iconset, f"icon_{n}x{n}{'@2x' if scale == 2 else ''}.png"), "wb") as fh:
                    fh.write(png_bytes(m, m, imgs[m]))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", os.path.join(out_dir, "icon.icns")], check=True)
        shutil.rmtree(tmp)
    print("icone in", out_dir)


def web(out_dir):
    """Icone per il browser: favicon.ico (16/32/48), icon.png (256, schede e "Aggiungi a Home"), icon-512.png."""
    os.makedirs(out_dir, exist_ok=True)
    S = 1024
    big = draw(S)
    imgs = {n: downscale(big, S, n) for n in (16, 32, 64, 256, 512)}
    data = [png_bytes(n, n, imgs[n]) for n in (16, 32, 64)]
    head = struct.pack("<HHH", 0, 1, len(data))
    offset, entries = 6 + 16 * len(data), b""
    for n, d in zip((16, 32, 64), data):
        entries += struct.pack("<BBBBHHII", n, n, 0, 0, 1, 32, len(d), offset)
        offset += len(d)
    with open(os.path.join(out_dir, "favicon.ico"), "wb") as fh:
        fh.write(head + entries + b"".join(data))
    for n, name in ((256, "icon.png"), (512, "icon-512.png")):
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(png_bytes(n, n, imgs[n]))
    print("icone web in", out_dir)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--web":
        web(sys.argv[2])
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else ".")
