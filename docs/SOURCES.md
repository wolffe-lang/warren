# Sources

warren is written in a clean room. This file records every document actually
consulted, with a digest where the document is a file, and what it was used
for. The lists of what may and may not be read are in the README.

## Consulted for the scaffold (2026-11-12)

| Reference | Identity | Use |
|---|---|---|
| wolf release v0.2.39 | release metadata read twice (`tests/pin-read-1.json`, `-2.json`); archive digests in `wolf-toolchain.toml` | the compiler pin |
| lupin release v0.1.61 | the same | the reference interpreter pin |
| wolf-std commit `77cf3210a82c93dc05ded987c249bb69e79b0a89` | tree `8ed51cc10bbe18b2fc7734c802af84422873899f` | the standard library pin; its `std.term` and `std.process` documentation for the pseudo-terminal and session calls the server will use |
| Organisation code: sniff's and burrow's `ci/` and `tools/` | their trunks | the shape of the tier planner, the gate and the toolchain fetcher |

## Incidental exposure

None.
