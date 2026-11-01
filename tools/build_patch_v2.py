# -*- coding: utf-8 -*-
"""
build_patch_v2.py — ChuSinGura46+1 Chinese patch, v2 layout:
keep every unchanged object at its ORIGINAL offset, append the 121 replaced
TextAsset blobs at end-of-file, patch their object-table entries in place.
Then emit delta ops (COPY/INSERT) vs the pristine original, verify replay,
and write the deflated delta used by the installer.

Also verifies the v2 file is semantically identical to the reference
(UnityPy-rebuilt) patched file: same objects, same raw bytes per path_id.

Usage: python build_patch_v2.py <orig> <patched_ref> <out_assets> <out_delta>
"""
import struct
import sys
import zlib
import UnityPy


def raw_script(data):
    return data.m_Script.encode("utf-8", "surrogateescape")


def find_script_start(raw, name, script):
    for namepad in range(0, 4):
        needle = struct.pack("<I", len(name)) + name + b"\0" * namepad
        p = raw.find(needle)
        while p != -1:
            cand = p + len(needle)
            if len(raw) >= cand + 4:
                slen = struct.unpack_from("<I", raw, cand)[0]
                if slen == len(script) and raw[cand + 4:cand + 4 + len(script)] == script:
                    return cand
            p = raw.find(needle, p + 1)
    return None


def varint(out, v):
    while True:
        b = v & 0x7F
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            break


def main():
    orig_path, patched_path, out_assets, out_delta = sys.argv[1:5]
    orig = open(orig_path, "rb").read()

    env_o = UnityPy.load(orig_path)
    env_p = UnityPy.load(patched_path)
    hdr = env_o.file.header
    data_offset = hdr.data_offset
    objs_o = {o.path_id: o for o in env_o.objects}
    objs_p = {o.path_id: o for o in env_p.objects}
    assert set(objs_o) == set(objs_p)
    table_order = list(env_o.objects)

    # ---- locate entry table (validated against every object) ---------------
    meta = orig[20:data_offset]
    t0 = table_order[0]
    pid_bytes = struct.pack("<q", t0.path_id)
    positions = [i for i in range(0, len(meta) - 25) if meta[i:i + 8] == pid_bytes]
    entry_size = entry_pos = None
    for E in (28, 25, 26, 24, 22, 20, 32):
        for pos in positions:
            ok = all(
                (lambda off: struct.unpack_from("<q", meta, off)[0] == ro.path_id
                 and struct.unpack_from("<II", meta, off + 8)
                 == (ro.byte_start - data_offset, ro.byte_size))(pos + i * E)
                for i, ro in enumerate(table_order)
            )
            if ok:
                entry_size, entry_pos = E, pos
                break
        if entry_size:
            break
    assert entry_size, "entry table not located"
    print(f"entry table @file {20 + entry_pos}, stride {entry_size}, {len(table_order)} entries")

    # ---- collect changed TextAssets & build replacement blobs --------------
    repl = {}  # path_id -> new object bytes
    for pid, ro in objs_o.items():
        if ro.type.name != "TextAsset":
            continue
        do, dp = ro.read(), objs_p[pid].read()
        if raw_script(do) == raw_script(dp):
            continue
        raw_o = ro.get_raw_data()
        raw_p = objs_p[pid].get_raw_data()
        so = find_script_start(raw_o, do.m_Name.encode(), raw_script(do))
        sp = find_script_start(raw_p, dp.m_Name.encode(), raw_script(dp))
        assert so is not None and sp is not None and raw_o[:so] == raw_p[:sp], pid
        repl[pid] = raw_o[:so] + raw_p[sp:]
    print(f"replaced TextAssets: {len(repl)}")

    # ---- build v2 file ------------------------------------------------------
    out = bytearray(orig)
    append_pos = len(orig)
    append_pad = (8 - (append_pos - data_offset) % 8) % 8
    append = bytearray(b"\0" * append_pad)
    cur = append_pos + append_pad
    new_off = {}
    for pid, blob in repl.items():          # table order for determinism
        if pid in repl:
            pass
    for ro in table_order:
        if ro.path_id in repl:
            blob = repl[ro.path_id]
            new_off[ro.path_id] = (cur, len(blob))
            append += blob
            cur += len(blob)
    out += append
    # patch entries
    for i, ro in enumerate(table_order):
        if ro.path_id in new_off:
            off = 20 + entry_pos + i * entry_size + 8
            ns, nlen = new_off[ro.path_id]
            struct.pack_into("<II", out, off, ns - data_offset, nlen)
    # header fileSize (big-endian u32 @4)
    struct.pack_into(">I", out, 4, len(out))
    open(out_assets, "wb").write(out)
    print(f"v2 assets written: {len(out):,} bytes (orig {len(orig):,})")

    # ---- semantic equivalence vs reference patched file ---------------------
    env_v = UnityPy.load(out_assets)
    objs_v = {o.path_id: o for o in env_v.objects}
    assert set(objs_v) == set(objs_p), "path_id set mismatch"
    mism = [pid for pid in objs_v if objs_v[pid].get_raw_data() != objs_p[pid].get_raw_data()]
    print(f"semantic check vs reference: object mismatches = {len(mism)}")
    assert not mism

    # ---- emit delta ops (COPY from orig / INSERT literal) -------------------
    ops = []

    def emit_copy(off, ln):
        if ln <= 0:
            return
        if ops and ops[-1][0] == "C" and ops[-1][1] + ops[-1][2] == off:
            ops[-1] = ("C", ops[-1][1], ops[-1][2] + ln)
        else:
            ops.append(("C", off, ln))

    # header: [COPY 0..4][INSERT fileSize][COPY 8..first patch]
    emit_copy(0, 4)
    ops.append(("I", struct.pack(">I", len(out))))
    patches = sorted(
        (20 + entry_pos + i * entry_size + 8,
         struct.pack("<II", new_off[ro.path_id][0] - data_offset, new_off[ro.path_id][1]))
        for i, ro in enumerate(table_order) if ro.path_id in new_off
    )
    pos = 8
    for poff, pbytes in patches:
        emit_copy(pos, poff - pos)
        ops.append(("I", pbytes))
        pos = poff + 8
    # everything from last patch to EOF of orig is unchanged; then appended tail
    emit_copy(pos, len(orig) - pos)
    if len(out) > len(orig):
        ops.append(("I", bytes(out[len(orig):])))
    print(f"delta ops: {len(ops)}")

    # ---- verify replay -------------------------------------------------------
    buf = bytearray(len(out))
    w = 0
    for op in ops:
        if op[0] == "C":
            buf[w:w + op[2]] = orig[op[1]:op[1] + op[2]]
            w += op[2]
        else:
            buf[w:w + len(op[1])] = op[1]
            w += len(op[1])
    assert w == len(out) and bytes(buf) == bytes(out), "replay mismatch!"
    print("replay: byte-exact OK")

    # ---- serialize ------------------------------------------------------------
    blob = bytearray(b"CZP2")
    blob += len(out).to_bytes(8, "little")
    varint(blob, len(ops))
    for op in ops:
        if op[0] == "C":
            blob.append(0x01)
            varint(blob, op[1])
            varint(blob, op[2])
        else:
            blob.append(0x02)
            varint(blob, len(op[1]))
            blob += op[1]
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    packed = comp.compress(bytes(blob)) + comp.flush()
    open(out_delta, "wb").write(packed)
    print(f"raw ops {len(blob):,} -> deflated {len(packed):,} -> {out_delta}")


if __name__ == "__main__":
    main()
