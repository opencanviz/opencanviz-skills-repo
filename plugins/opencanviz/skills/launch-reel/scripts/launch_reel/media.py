"""Screenshots for the screenshot scene. The renderer reads a frame's pixels back to encode it,
which a cross-origin image would taint, so every image is embedded as a data URI: a local path
or a URL in, `{image, image_w, image_h}` out, scaled down to a sensible width first."""
from __future__ import annotations

import base64
import io
import urllib.request
from pathlib import Path

MAX_W = 2000


def embed_image(src: str, max_w: int = MAX_W) -> dict:
    """A screenshot as `{image, image_w, image_h}`. Needs Pillow (`pip install pillow`)."""
    try:
        from PIL import Image
    except ImportError as e:
        raise SystemExit("screenshots need Pillow: pip install pillow") from e
    if src.startswith("data:"):
        raw = base64.b64decode(src.split(",", 1)[1])
    elif src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0 launch-reel"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(20_000_000)
    else:
        raw = Path(src).expanduser().read_bytes()
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    if im.mode in ("RGBA", "LA", "P"):
        im.save(buf, "PNG", optimize=True)
        mime = "image/png"
    else:
        im.convert("RGB").save(buf, "JPEG", quality=88)
        mime = "image/jpeg"
    return {"image": f"data:{mime};base64," + base64.b64encode(buf.getvalue()).decode(),
            "image_w": im.width, "image_h": im.height}


def attach_screenshots(spec: dict, shots: list[dict]) -> dict:
    """Give the spec's screenshot scenes their images in order. Screenshots the spec has no scene
    for get a plain browser-framed scene each, before the end card."""
    shots = list(shots or [])
    for sc in spec.get("scenes") or []:
        if sc.get("type") == "screenshot" and not str(sc.get("image") or "").startswith("data:"):
            if str(sc.get("image") or "") and not shots:
                sc.update(embed_image(sc["image"]))
            elif shots:
                sc.update(shots.pop(0))
    scenes = spec.setdefault("scenes", [])
    at = next((i for i, s in enumerate(scenes) if s.get("type") == "end"), len(scenes))
    for sh in shots:
        scenes.insert(at, {"type": "screenshot", "frame": "browser", **sh})
        at += 1
    return spec
