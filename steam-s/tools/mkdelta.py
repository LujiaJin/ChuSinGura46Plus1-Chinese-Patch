# -*- coding: utf-8 -*-
"""
mkdelta.py — generate compact binary deltas (orig -> patched) for the
ChuSinGura46+1 Chinese localization patch.

Delta format (before compression):
  magic  b"CZP1"
  u64    new_size (little endian)
  varint op_count
  ops:
    0x01 COPY  varint orig_offset, varint length
    0x02 INSERT varint length, raw bytes
The op stream is deflate-compressed (raw, wbits=-15) so C# DeflateStream
can decompress it with no external dependencies.

Usage: python mkdelta.py <orig> <new> <out.bin>
Writes out.bin and verifies reconstruction byte-for-byte.
"""
import hashlib
import sys
import zlib

CHUNK = 1 << 20
NEEDLE = 512
WINDOW = 64 << 20  # generous resync window


def common_prefix(o, n, po, pp):
    """Length of equal run of o[po:] and n[pp:], memcmp speed via chunk slices."""
    max_l = min(len(o) - po, len(n) - pp)
    if max_l == 0:
        return 0
    lo = 0
    # chunk compare
    while lo < max_l:
        step = min(CHUNK, max_l - lo)
        if o[po + lo:po + lo + step] == n[pp + lo:pp + lo + step]:
            lo += step
        else:
            break
    if lo >= max_l:
        return max_l
    # binary refine inside the failing chunk region [lo, lo+step)
    hi = min(lo + min(CHUNK, max_l - lo), max_l)
    while lo < hi:
        # find first mismatch in (lo, hi]
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if o[po + lo:po + mid] == n[pp + lo:pp + mid]:
                lo = mid
            else:
                hi = mid
        break
    return lo


def resync(o, n, po, pp, span=8192, K=64):
    """Find forward sync pair (o2>=po, p2>=pp) with o[o2:o2+K]==n[p2:p2+K],
    preferring the earliest advance in new. Returns None if not found."""
    o_end = min(po + span, len(o) - K)
    if o_end < po:
        return None
    index = {}
    oc = o
    for i in range(po, o_end + 1):
        key = oc[i:i + K]
        if key not in index:
            index[key] = i
    n_end = min(pp + span, len(n) - K)
    for j in range(pp, n_end + 1):
        i = index.get(n[j:j + K])
        if i is not None:
            return (i, j)
    return None


def gen_delta(o, n):
    ops = []
    po = pp = 0
    No, Nn = len(o), len(n)

    def emit_copy(off, ln):
        if ln <= 0:
            return
        if ops and ops[-1][0] == "C" and ops[-1][1] + ops[-1][2] == off:
            ops[-1] = ("C", ops[-1][1], ops[-1][2] + ln)
        else:
            ops.append(("C", off, ln))

    ins_buf = bytearray()

    def flush_ins():
        nonlocal ins_buf
        if ins_buf:
            ops.append(("I", bytes(ins_buf)))
            ins_buf = bytearray()

    while pp < Nn:
        eq = common_prefix(o, n, po, pp)
        if eq > 0:
            flush_ins()
            emit_copy(po, eq)
            po += eq
            pp += eq
            continue
        # divergence: find sync pair
        pair = resync(o, n, po, pp)
        if pair is None:
            # wide-window fallback before giving up
            nlen_o = min(NEEDLE, No - po)
            a = n.find(o[po:po + nlen_o], pp, min(pp + WINDOW, Nn)) if nlen_o > 0 else -1
            nlen_n = min(NEEDLE, Nn - pp)
            b_found = o.find(n[pp:pp + nlen_n], po, min(po + WINDOW, No)) if nlen_n > 0 else -1
            if a == -1 and b_found == -1:
                ins_buf += n[pp:]
                pp = Nn
                break
            if a != -1 and (b_found == -1 or a <= (b_found - po)):
                pair = (po, a)
            else:
                pair = (b_found, pp)
        o2, p2 = pair
        if o2 > po:
            flush_ins()          # orig bytes dropped/replaced
            po = o2
        if p2 > pp:
            ins_buf += n[pp:p2]  # new bytes inserted/modified
            pp = p2
    flush_ins()
    return ops


def serialize(ops, new_size):
    out = bytearray()
    out += b"CZP1"
    out += new_size.to_bytes(8, "little")

    def varint(v):
        while True:
            b = v & 0x7F
            v >>= 7
            if v:
                out.append(b | 0x80)
            else:
                out.append(b)
                break

    varint(len(ops))
    for op in ops:
        if op[0] == "C":
            out.append(0x01)
            varint(op[1])
            varint(op[2])
        else:
            out.append(0x02)
            varint(len(op[1]))
            out += op[1]
    return bytes(out)


def verify(o, ops, new, new_size):
    buf = bytearray(new_size)
    w = 0
    for op in ops:
        if op[0] == "C":
            buf[w:w + op[2]] = o[op[1]:op[1] + op[2]]
            w += op[2]
        else:
            buf[w:w + len(op[1])] = op[1]
            w += len(op[1])
    assert w == new_size, f"size mismatch {w} != {new_size}"
    assert bytes(buf) == new, "reconstruction mismatch!"
    return True


def main():
    orig_path, new_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    o = open(orig_path, "rb").read()
    n = open(new_path, "rb").read()
    print(f"orig={len(o):,} new={len(n):,}")
    ops = gen_delta(o, n)
    n_copy = sum(op[2] for op in ops if op[0] == "C")
    n_ins = sum(len(op[1]) for op in ops if op[0] == "I")
    print(f"ops={len(ops)} (copy={sum(1 for x in ops if x[0]=='C')}, insert={sum(1 for x in ops if x[0]=='I')})")
    print(f"copy bytes={n_copy:,}  insert bytes={n_ins:,}")
    verify(o, ops, n, len(n))
    print("verify: byte-exact reconstruction OK")
    blob = serialize(ops, len(n))
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = comp.compress(blob) + comp.flush()
    open(out_path, "wb").write(packed)
    print(f"raw ops={len(blob):,}  deflated={len(packed):,} -> {out_path}")


if __name__ == "__main__":
    main()
