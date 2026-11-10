# campion-pbqp-corpus

PBQP register allocation graphs dumped from LLVM's PBQP register allocator over
open-source C programs. [campion](https://github.com/zayenz/campion) uses them as
the compiler track of its PBQP benchmarks. Every graph is in campion's
`.pbqpgraph` format.

## Provenance

campion's `just pbqp-llvm-corpus` built the corpus from the inputs pinned in
campion's `benchmarks/pbqp-llvm-corpus.toml` (campion commit `1b72184`). Every
archive is pinned by URL and sha256; `manifest.json` records them all.

- LLVM and clang 23.1.5, built with assertions on so that `-pbqp-dump-graphs`
  exists, targets AArch64 and X86.
- Headers: musl 1.2.5, so the result does not depend on the host SDK.
- Targets: `x86_64-unknown-linux-musl` and `aarch64-unknown-linux-musl`.
- clang flags: `--target=<target> -O2 -g0 -w -nostdlibinc -S -emit-llvm`, plus
  each program's own defines.
- llc flags: `-O2 -regalloc=pbqp -pbqp-dump-graphs`.

| Program | Version | Licence | Graphs |
|---|---|---|---|
| zlib | 1.3.1 | Zlib | 249 |
| bzip2 | 1.0.8 | bzip2-1.0.6 | 149 |
| lua | 5.4.7 | MIT | 1,316 |
| sqlite (amalgamation) | 3.50.4 | blessing | 4,006 |
| mbedtls | 3.6.4 | Apache-2.0 OR GPL-2.0-or-later | 3,054 |
| XSBench (LLVM test-suite) | 23.1.5 | MIT | 53 |
| RSBench (LLVM test-suite) | 23.1.5 | MIT AND Apache-2.0 WITH LLVM-exception | 63 |
| SimpleMOC (LLVM test-suite) | 23.1.5 | MIT AND Apache-2.0 WITH LLVM-exception | 97 |
| miniGMG (LLVM test-suite) | 23.1.5 | BSD-3-Clause-LBNL | 141 |
| CoMD (LLVM test-suite) | 23.1.5 | BSD-3-Clause | 165 |
| Stanford (LLVM test-suite) | 23.1.5 | Apache-2.0 WITH LLVM-exception AND NCSA | 110 |

That is 9,403 accepted graphs, 25.7 GB uncompressed. The pipeline drops
duplicates and unreadable dumps; `manifest.json` lists the 938 rejected graphs
with their reasons.

## Licences

Each graph is data derived from its source program and carries that program's
licence, given as an SPDX expression in the graph's `licence` field in
`manifest.json`. The licence texts are in `licences/<program>/`, copied from the
program archives. No program here forbids redistribution; SPEC and similar suites
are never included.

## Files in this repository

- `manifest.json`: the corpus manifest the pipeline wrote, with every accepted
  graph's id, file, sha256 (of the uncompressed graph), program, licence, target,
  flags, node and edge counts. Its sha256 is
  `6e61e19aaabceafc2ddeffa8e17cd1fbae559d3cf11cd9ed11d5b4e1c49916a3`.
- `licences/`: the licence texts.
- `subset.json`: the published checksum manifest. It records the full archive and
  every subset asset with its release URL and the sha256 of the `.zst` file as
  downloaded, plus the graph's id and the sha256 of the uncompressed graph.
- `prepare_release.py`: builds the release assets from a local corpus.

No graphs are committed here.

## Release layout

Release `v1` has these assets, all flat:

- `campion-pbqp-corpus-v1.tar.zst` and `campion-pbqp-corpus-v1.tar.zst.sha256`:
  the whole corpus, a tar of `campion-pbqp-corpus/{manifest.json,licences,graphs}`
  compressed with `zstd -19 --long=27`. Decompress it with the same window:

      zstd -d --long=27 -c campion-pbqp-corpus-v1.tar.zst | tar -x

- `<id>.pbqpgraph.zst`: the benchmark subset, one graph per asset compressed with
  `zstd -19`. The asset name is the graph id from `manifest.json` with `/`
  replaced by `__`, so
  `x86_64-unknown-linux-musl/zlib/deflate.c/deflate.0` becomes
  `x86_64-unknown-linux-musl__zlib__deflate.c__deflate.0.pbqpgraph.zst`.
  campion reads `.zst` graphs directly.

URLs have the form
`https://github.com/zayenz/campion-pbqp-corpus/releases/download/v1/<asset>`.
The tag is never moved, so these URLs and checksums stay valid.

The subset is chosen deterministically to span the size distribution: sort the
graphs by (nodes, id) and take 150 evenly spaced ranks, do the same by
(edges, id), and add the 15 largest graphs by nodes and the 15 largest by edges.
The union is the subset; `subset.json` holds the exact list.

## Download and check a sample

These five subset assets range from a 1-node graph to the largest graph by edges
(1,234 nodes, 94,096 edges):

    base=https://github.com/zayenz/campion-pbqp-corpus/releases/download/v1
    for a in aarch64-unknown-linux-musl__bzip2__bzlib.c__BZ2_bzlibVersion.0.pbqpgraph.zst \
      x86_64-unknown-linux-musl__sqlite__sqlite3.c__sqlite3RowSetClear.0.pbqpgraph.zst \
      x86_64-unknown-linux-musl__mbedtls__library__cipher.c__mbedtls_cipher_set_iv.0.pbqpgraph.zst \
      aarch64-unknown-linux-musl__lua__src__lobject.c__luaO_str2num.0.pbqpgraph.zst \
      aarch64-unknown-linux-musl__sqlite__sqlite3.c__sqlite3_str_vappendf.0.pbqpgraph.zst; do curl -fLO "$base/$a"; done
    python3 -c 'import json,hashlib,sys
    m={g["asset"]:g["sha256"] for g in json.load(open(sys.argv[1]))["graphs"]}
    for a in sys.argv[2:]:
        ok=hashlib.sha256(open(a,"rb").read()).hexdigest()==m[a]
        print("ok " if ok else "BAD", a)' subset.json *.pbqpgraph.zst

and solve one with campion:

    campion pbqp solve --algorithm rn-llvm <asset>.pbqpgraph.zst

## Regenerate

In a campion checkout at commit `1b72184`:

    just pbqp-llvm-corpus

This downloads the pinned archives, builds LLVM, compiles every program for both
targets and writes `target/pbqp-corpus/run/corpus`. Its `manifest.json` should
have the sha256 above. Then, with zstd 1.5.7, in this repository:

    python3 prepare_release.py <campion>/target/pbqp-corpus/run/corpus <out> v1

writes the release assets to `<out>` and refreshes `manifest.json`, `licences/`
and `subset.json` here. Another zstd version may compress to other bytes; the
graphs inside are unchanged.
