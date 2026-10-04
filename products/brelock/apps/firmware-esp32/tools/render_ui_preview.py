"""Render the actual firmware drawing code, not a separate UI mock-up."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=root / "output/device-ui")
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
gfx = root / ".pio/libdeps/waveshare-s3-touch/Adafruit GFX Library"
with tempfile.TemporaryDirectory(prefix="brelock-ui-render-") as folder:
    executable = Path(folder) / "render"
    subprocess.run([
        shutil.which("clang++") or "g++", "-std=c++11", "-DARDUINO=100",
        "-I", str(root / "tools/ui-preview-mocks"), "-I", str(gfx),
        "-I", str(root / "include"), str(gfx / "Adafruit_GFX.cpp"),
        str(root / "src/ui_renderer.cpp"), str(root / "tools/ui_preview.cpp"),
        "-o", str(executable),
    ], check=True)
    subprocess.run([str(executable), str(args.output)], check=True)
sheet = Image.new("RGB", (820, 1190), "#101827")
draw = ImageDraw.Draw(sheet)
names = ["Ochrona", "Dystans", "Kalibracja", "Blokada", "Przytrzymanie blokady", "Brak połączenia",
         "Przytrzymanie kalibracji", "Pomiar 3 m", "Zapisano",
         "Przejście na 2 m", "Potwierdź 1 m", "Potwierdź 3 m"]
for i, label in enumerate(names):
    picture = Image.open(args.output / f"{i}.ppm").convert("RGB")
    mask = Image.new("L", (240, 240), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 239, 239), fill=255)
    x, y = 20 + i % 3 * 270, 20 + i // 3 * 295
    sheet.paste(picture, (x, y), mask)
    draw.text((x + 25, y + 250), label, fill="#b7c8df")
    picture.save(args.output / f"{i}.png")
    (args.output / f"{i}.ppm").unlink()
sheet.save(args.output / "device-ui.png")
print(args.output / "device-ui.png")
