#!/usr/bin/env python3
"""Prepares the release assets of campion-pbqp-corpus from a local corpus.

Usage: prepare_release.py CORPUS OUT TAG

CORPUS is the directory that campion's `just pbqp-llvm-corpus` writes
(target/pbqp-corpus/run/corpus): manifest.json, graphs/ and licences/. The script

1. copies manifest.json and licences/ into this repository;
2. writes OUT/campion-pbqp-corpus-TAG.tar.zst, a tar of manifest.json, licences/ and
   graphs/ with sorted members, mtime 0 and uid/gid 0, compressed with
   `zstd -19 --long=27`, and its .sha256;
3. selects the benchmark subset (see `select`), compresses each graph on its own with
   `zstd -19` into OUT/<asset>, where <asset> is the graph id with "/" replaced by
   "__" plus ".pbqpgraph.zst";
4. writes subset.json, with each subset graph's id, asset, release URL, sha256 of the
   .zst file, sha256 of the graph, program, licence, target, nodes and edges.

Run it with zstd 1.5.7; another zstd version may give other compressed bytes.
"""
import hashlib, json, shutil, subprocess, sys, tarfile
from pathlib import Path

REPO = "https://github.com/zayenz/campion-pbqp-corpus"
SPREAD = 150   # evenly spaced graphs by node rank and by edge rank
LARGEST = 15   # the largest graphs by nodes and by edges


def select(graphs):
    """Deterministic subset spanning the node and edge distribution."""
    chosen = set()
    for key in ("nodes", "edges"):
        ranked = sorted(graphs, key=lambda g: (g[key], g["id"]))
        n = len(ranked)
        chosen.update(ranked[round(i * (n - 1) / (SPREAD - 1))]["id"] for i in range(SPREAD))
        chosen.update(g["id"] for g in ranked[-LARGEST:])
    return [g for g in sorted(graphs, key=lambda g: g["id"]) if g["id"] in chosen]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def archive(corpus, out, name):
    def clean(info):
        info.mtime = 0
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mode = 0o755 if info.isdir() else 0o644
        return info

    def add(tar, path, arc):
        tar.add(path, arc, recursive=False, filter=clean)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                add(tar, child, f"{arc}/{child.name}")

    target = out / name
    with open(target, "wb") as dst:
        zstd = subprocess.Popen(["zstd", "-19", "--long=27", "-T0", "-q", "-c"],
                                stdin=subprocess.PIPE, stdout=dst)
        with tarfile.open(fileobj=zstd.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
            for top in ("manifest.json", "licences", "graphs"):
                add(tar, corpus / top, f"campion-pbqp-corpus/{top}")
        zstd.stdin.close()
        if zstd.wait():
            sys.exit("zstd failed")
    (out / f"{name}.sha256").write_text(f"{sha256(target)}  {name}\n")


def main():
    corpus, out, tag = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    repo = Path(__file__).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((corpus / "manifest.json").read_text())
    shutil.copyfile(corpus / "manifest.json", repo / "manifest.json")
    shutil.rmtree(repo / "licences", ignore_errors=True)
    shutil.copytree(corpus / "licences", repo / "licences")

    entries = []
    for g in select(manifest["graphs"]):
        asset = g["id"].replace("/", "__") + ".pbqpgraph.zst"
        subprocess.run(["zstd", "-19", "-q", "-f", str(corpus / g["file"]), "-o", str(out / asset)],
                       check=True)
        entries.append({
            "id": g["id"], "asset": asset,
            "url": f"{REPO}/releases/download/{tag}/{asset}",
            "sha256": sha256(out / asset), "graph_sha256": g["sha256"],
            **{k: g[k] for k in ("program", "version", "licence", "target", "nodes", "edges")},
        })

    name = f"campion-pbqp-corpus-{tag}.tar.zst"
    archive(corpus, out, name)
    subset = {
        "schema_version": 1, "tag": tag,
        "corpus_manifest_sha256": sha256(corpus / "manifest.json"),
        "zstd": subprocess.run(["zstd", "-V"], capture_output=True, text=True).stdout.strip(),
        "archive": {"asset": name, "url": f"{REPO}/releases/download/{tag}/{name}",
                    "sha256": sha256(out / name), "compression": "zstd -19 --long=27"},
        "subset_rule": f"{SPREAD} evenly spaced by node rank and by edge rank (ties by id), "
                       f"plus the {LARGEST} largest by nodes and by edges",
        "subset_compression": "zstd -19",
        "graphs": entries,
    }
    (repo / "subset.json").write_text(json.dumps(subset, indent=2) + "\n")
    print(f"{len(entries)} subset graphs; archive {(out / name).stat().st_size} bytes")


if __name__ == "__main__":
    main()
