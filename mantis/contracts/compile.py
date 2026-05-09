"""Compile AlphaSignalRegistry.sol and dump ABI + bytecode to JSON."""

from __future__ import annotations

import json
from pathlib import Path

import solcx

SOLC_VERSION = "0.8.28"
CONTRACT_NAME = "AlphaSignalRegistry"
SOL_FILE = Path(__file__).parent / f"{CONTRACT_NAME}.sol"
OUTPUT_FILE = Path(__file__).parent / f"{CONTRACT_NAME}.json"


def compile_contract() -> dict:
    solcx.install_solc(SOLC_VERSION, show_progress=True)
    solcx.set_solc_version(SOLC_VERSION)

    compiled = solcx.compile_files(
        [str(SOL_FILE)],
        output_values=["abi", "bin"],
        solc_version=SOLC_VERSION,
    )

    key = next(k for k in compiled if CONTRACT_NAME in k)
    abi = compiled[key]["abi"]
    bytecode = compiled[key]["bin"]

    artifact = {"abi": abi, "bytecode": bytecode}
    OUTPUT_FILE.write_text(json.dumps(artifact, indent=2))
    print(f"Wrote {OUTPUT_FILE} ({len(abi)} ABI entries, {len(bytecode)//2} bytes)")
    return artifact


if __name__ == "__main__":
    compile_contract()
