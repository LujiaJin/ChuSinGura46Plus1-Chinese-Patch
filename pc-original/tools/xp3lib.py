
"""ChuSinGura46+1 XP3 repacker - exact format match with game engine.
Storage order per file: encrypt(zlib(plaintext), offset=0, adler32(plaintext))
Table entry sections in order: time, adlr, segm, info
"""
import struct, zlib

XP3_MAGIC = b"XP3\r\n \n\x1a\x8b\x67\x01"

def make_table(adler):
    key = adler & 0x1FFFFFFF
    key |= (key & 1) << 29
    table = bytearray(29)
    for i in range(29):
        table[i] = key & 0xFF
        key = (key >> 8) | ((key << 21) & 0xFF000000)
    return bytes(table)

def encrypt(buf, offset, adler):
    t = make_table(adler)
    n = len(buf)
    if n == 0: return buf
    start = (-offset) % 29
    ks = (t * (n // 29 + 2))[start:start+n]
    return (int.from_bytes(buf, 'little') ^ int.from_bytes(ks, 'little')).to_bytes(n, 'little')

def build_xp3(files):
    """files: list of (name, plaintext_bytes). Returns complete XP3 as bytes."""
    HEADER_SIZE = 19
    data_area = bytearray()
    table_entries = []
    for name, plain in files:
        adler = zlib.adler32(plain) & 0xFFFFFFFF
        encrypted = encrypt(plain, 0, adler)
        stored = zlib.compress(encrypted, 9)
        offset = HEADER_SIZE + len(data_area)
        data_area += stored
        nlen = len(name)
        info_size = 22 + nlen*2 + 2
        entry = b""
        # time section (8 bytes: dummy FILETIME)
        entry += b"time" + struct.pack("<q", 8) + struct.pack("<q", 0)
        # adlr section
        entry += b"adlr" + struct.pack("<q", 4) + struct.pack("<I", adler)
        # segm section: u32 flag(1=zlib) + u64 offset + u64 usize + u64 csize
        entry += b"segm" + struct.pack("<q", 28) + struct.pack("<IQQQ", 1, offset, len(plain), len(stored))
        # info section: u32 flags + u64 usize + u64 csize + u16 namelen + name + u16 null
        info_data = struct.pack("<IQQH", 0x80000000, len(plain), len(stored), nlen)
        info_data += name.encode("utf-16-le") + b"\x00\x00"
        entry += b"info" + struct.pack("<q", info_size) + info_data
        table_entries.append(b"File" + struct.pack("<q", len(entry)) + entry)
    table = b"".join(table_entries)
    table_comp = zlib.compress(table, 9)
    table_offset = HEADER_SIZE + len(data_area)
    out = XP3_MAGIC + struct.pack("<q", table_offset)
    out += bytes(data_area)
    out += struct.pack("<Bqq", 1, len(table_comp), len(table)) + table_comp
    return out

def read_xp3(path):
    """Full round-trip reader for verification."""
    data = open(path, "rb").read()
    tbl_off = struct.unpack_from("<q", data, 11)[0]
    first = struct.unpack_from("<I", data, tbl_off)[0]
    if first == 0x80:
        tbl_off = struct.unpack_from("<q", data, tbl_off + 9)[0]
    ht = data[tbl_off]
    ps = struct.unpack_from("<q", data, tbl_off+1)[0]
    table = zlib.decompress(data[tbl_off+17:tbl_off+17+ps])
    out = {}
    tpos = 0
    while tpos < len(table) - 12:
        if table[tpos:tpos+4] != b"File": break
        esize = struct.unpack_from("<q", table, tpos+4)[0]
        ed = table[tpos+12:tpos+12+esize]
        epos = 0; info=segm=adlr=None
        while epos < len(ed) - 12:
            sec = ed[epos:epos+4]; ss = struct.unpack_from("<q", ed, epos+4)[0]
            sd = ed[epos+12:epos+12+ss]
            if sec == b"info":
                flags = struct.unpack_from("<I", sd, 0)[0]
                usize = struct.unpack_from("<Q", sd, 4)[0]
                nlen = struct.unpack_from("<H", sd, 20)[0]
                name = sd[22:22+nlen*2].decode("utf-16-le").rstrip("\x00")
                info = (flags, usize, name)
            elif sec == b"segm":
                segm = struct.unpack("<IQQQ", sd[:28])
            elif sec == b"adlr":
                adlr = struct.unpack("<I", sd[:4])[0]
            epos += 12 + ss
        if info:
            sf, off, us, cs = segm
            raw = data[off:off+cs]
            if sf == 1: raw = zlib.decompress(raw)
            if info[0] & 0x80000000:
                t = make_table(adlr)
                n = len(raw)
                ks = (t * (n // 29 + 2))[0:n]
                raw = (int.from_bytes(raw, 'little') ^ int.from_bytes(ks, 'little')).to_bytes(n, 'little')
            assert (zlib.adler32(raw) & 0xFFFFFFFF) == adlr, f"roundtrip fail {info[2]}"
            out[info[2]] = raw
        tpos += 12 + esize
    return out

if __name__ == "__main__":
    import sys, os
    # Self-test: build from decrypted scenario + verify round trip
    src = r"D:\Games\Chusingura46+1\decrypted2\scenario"
    names = ["about.ks", "first.ks", "C-001.KS", "Y-001a.KS", "free.txt"]
    files = [(n, open(os.path.join(src, n), "rb").read()) for n in names]
    xp3 = build_xp3(files)
    open(r"D:\Games\Chusingura46+1\Tools\pipeline\selftest.xp3", "wb").write(xp3)
    back = read_xp3(r"D:\Games\Chusingura46+1\Tools\pipeline\selftest.xp3")
    for n, orig in files:
        assert back[n] == orig, f"MISMATCH {n}"
    print(f"SELF-TEST OK: {len(files)} files, xp3={len(xp3):,}B, roundtrip perfect")
