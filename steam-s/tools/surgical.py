# -*- coding: utf-8 -*-
"""
surgical.py — build a *minimally modified* patched resources.assets for the
ChuSinGura46+1 Chinese localization, by transplanting only the changed
TextAsset object bytes from the UnityPy-rebuilt patched file into the
ORIGINAL file's byte layout, rewriting object-table offsets/sizes.

Output is functionally equivalent to the verified patched file but keeps
~99% of original bytes in place -> tiny binary delta.

Usage: python surgical.py <orig> <patched_ref> <out>
"""
import struct
import sys
import UnityPy


def raw_script(data):
    """m_Script raw bytes (the file may contain non-UTF8; UnityPy decodes with surrogateescape)."""
    return data.m_Script.encode("utf-8", "surrogateescape")


def main():
    orig_path, patched_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    orig_bytes = open(orig_path, "rb").read()
    patched_bytes = open(patched_path, "rb").read()

    env_o = UnityPy.load(orig_path)
    env_p = UnityPy.load(patched_path)

    hdr = env_o.file.header
    version = hdr.version
    data_offset = hdr.data_offset
    print(f"serialized header version={version} dataOffset={data_offset} "
          f"metadataSize={hdr.metadata_size} fileSize={hdr.file_size}")
    assert version < 22, "v>=22 layout not handled"

    objs_o = {o.path_id: o for o in env_o.objects}
    objs_p = {o.path_id: o for o in env_p.objects}
    print(f"objects orig={len(objs_o)} patched={len(objs_p)}")
    assert set(objs_o) == set(objs_p), "object path_id sets differ!"

    # ---- find changed TextAssets, verify prefix equality -------------------
    changed = {}   # path_id -> new object bytes (from patched file)
    for pid, ro in objs_o.items():
        if ro.type.name != "TextAsset":
            continue
        do = ro.read()
        dp = objs_p[pid].read()
        if raw_script(do) == raw_script(dp):
            continue
        raw_o = ro.get_raw_data()
        raw_p = objs_p[pid].get_raw_data()
        # find where m_Script section starts in each: parse [PPtr][m_Name str]
        # we transplant: orig_prefix + patched_tail, where tail = patched's
        # serialized m_Script (7-bit len + bytes + align). To locate it, use
        # the fact that everything before m_Script must be identical.
        # Strategy: locate orig's script-start by finding its serialized
        # length prefix via mini-parser; same for patched; then compare prefixes.
        so = find_script_start(raw_o, do.m_Name.encode("utf-8", "surrogateescape"),
                               raw_script(do))
        sp = find_script_start(raw_p, dp.m_Name.encode("utf-8", "surrogateescape"),
                               raw_script(dp))
        assert so is not None and sp is not None, f"script start not found pid={pid}"
        assert raw_o[:so] == raw_p[:sp], f"prefix mismatch pid={pid} ({do.m_Name})"
        changed[pid] = raw_o[:so] + raw_p[sp:]
    print(f"changed TextAssets: {len(changed)}")

    # ---- validate data region packing ---------------------------------------
    order = sorted(objs_o.values(), key=lambda o: o.byte_start)
    gaps = set()
    prev_end = None
    for ro in order:
        if prev_end is not None:
            gaps.add(ro.byte_start - prev_end)
        prev_end = ro.byte_start + ro.byte_size
    print(f"first obj at {order[0].byte_start}, inter-object gaps: {sorted(gaps)[:5]} ... "
          f"max={max(gaps)}")
    # we only support gap==0 (packed) or uniform alignment; handle generally:
    align = 0
    if gaps and max(gaps) > 0:
        # detect alignment: every byte_start % k == data_offset % k for some k
        for k in (8, 16):
            if all((ro.byte_start - data_offset) % k == 0 for ro in order):
                align = k
                break
        print(f"detected object alignment: {align}")

    # ---- locate object table entries in metadata ---------------------------
    # v15 entry: [i64 pathID][u32 startRel][u32 size][i32 typeID][u16 classID]
    #             [i16 scriptIdx][u8 stripped] = 25B, 4-aligned -> stride 28
    meta = orig_bytes[20:data_offset]
    table_order = list(env_o.objects)
    t0 = table_order[0]
    pid_bytes = struct.pack("<q", t0.path_id)
    positions = [i for i in range(0, len(meta) - 25) if meta[i:i + 8] == pid_bytes]
    print(f"anchor candidates for first entry (pathID={t0.path_id}): {len(positions)}")
    entry_size = None
    entry_pos = None

    def entry_ok(pos, E):
        if pos + len(table_order) * E > len(meta) + E:
            return False
        for i, ro in enumerate(table_order):
            off = pos + i * E
            pid = struct.unpack_from("<q", meta, off)[0]
            bsr, bsz = struct.unpack_from("<II", meta, off + 8)
            if pid != ro.path_id or bsr != ro.byte_start - data_offset or bsz != ro.byte_size:
                return False
        return True

    for E in (28, 25, 26, 24, 22, 20, 32):
        for pos in positions:
            if entry_ok(pos, E):
                entry_size, entry_pos = E, pos
                break
        if entry_size:
            break
    assert entry_size, "failed to locate/validate object table entries"
    print(f"object table: entry_size={entry_size} at file offset {20 + entry_pos}, "
          f"count={len(table_order)}")

    # ---- rebuild ------------------------------------------------------------
    out = bytearray(orig_bytes)
    # 1) rewrite data region: walk objects in TABLE order, place bytes
    #    sequentially at data_offset (replicating alignment if detected)
    new_data = bytearray()
    new_entries = {}
    cur = data_offset
    for ro in table_order:
        if align:
            pad = (align - (cur - data_offset) % align) % align
            new_data += b"\0" * pad
            cur += pad
        blob = changed.get(ro.path_id, orig_bytes[ro.byte_start:ro.byte_start + ro.byte_size])
        new_entries[ro.path_id] = (cur, len(blob))
        new_data += blob
        cur += len(blob)
    out[data_offset:] = new_data
    # 2) rewrite entries (byteStartRel @+8, byteSize @+12 for i64-pathID entries)
    for i, ro in enumerate(table_order):
        off = 20 + entry_pos + i * entry_size
        ns, nlen = new_entries[ro.path_id]
        struct.pack_into("<II", out, off + 8, ns - data_offset, nlen)
    # 3) header fileSize — NOTE: the 4 header u32s are BIG-endian in this file
    struct.pack_into(">I", out, 4, len(out))
    open(out_path, "wb").write(out)
    print(f"wrote {out_path}: {len(out):,} bytes")

    # ---- self validation via UnityPy ----------------------------------------
    env_n = UnityPy.load(out_path)
    assert len(list(env_n.objects)) == len(table_order), "object count changed!"
    n_changed_ok = 0
    for pid, ro in env_n.objects_dict.items() if hasattr(env_n, "objects_dict") else []:
        pass
    objs_n = {o.path_id: o for o in env_n.objects}
    for pid, newb in changed.items():
        assert objs_n[pid].get_raw_data() == newb, f"transplant mismatch pid={pid}"
        n_changed_ok += 1
    # all unchanged objects must be byte-identical & at identical content
    diff_pos = 0
    for pid, ro in objs_n.items():
        if pid in changed:
            continue
        a = ro.get_raw_data()
        b = orig_bytes[objs_o[pid].byte_start:objs_o[pid].byte_start + objs_o[pid].byte_size]
        if a != b:
            diff_pos += 1
    print(f"validation: {n_changed_ok} transplanted OK; unchanged-object mismatches: {diff_pos}")
    assert diff_pos == 0
    print("SURGICAL BUILD OK")


def find_script_start(raw: bytes, name: bytes, script: bytes):
    """Empirical layout (Unity 5.4 / serialized v15):
    [u32 nameLen][name bytes][u32 scriptLen][script bytes][pad]
    Returns the offset of the script length prefix."""
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


if __name__ == "__main__":
    main()
