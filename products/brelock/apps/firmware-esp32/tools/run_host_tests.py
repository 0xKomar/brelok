#!/usr/bin/env python3
"""Compile the real motion/protocol code on the host, without Arduino or a board."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    compiler = os.environ.get("CXX") or shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        raise SystemExit("C++ compiler required; set CXX or install clang++/g++.")
    with tempfile.TemporaryDirectory(prefix="brelock-firmware-tests-") as directory:
        executable = Path(directory) / "firmware_tests"
        subprocess.run(
            [
                compiler,
                "-std=c++11",
                "-Wall",
                "-Wextra",
                "-Wpedantic",
                "-Werror",
                "-I",
                str(root / "include"),
                str(root / "src/motion.cpp"),
                str(root / "src/telemetry.cpp"),
                str(root / "tests/firmware_tests.cpp"),
                "-o",
                str(executable),
            ],
            check=True,
        )
        subprocess.run([str(executable)], check=True)
        interaction = Path(directory) / "interaction_tests"
        subprocess.run([
            compiler, "-std=c++11", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
            "-I", str(root / "include"), str(root / "src/control.cpp"),
            str(root / "src/device_ui.cpp"), str(root / "tests/interaction_tests.cpp"),
            "-o", str(interaction),
        ], check=True)
        subprocess.run([str(interaction)], check=True)


if __name__ == "__main__":
    main()
