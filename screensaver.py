"""Animated screensaver sprites with optional equal-mass box collisions."""

from bisect import bisect_right
import io
import math
import random
import subprocess
import time

from PIL import Image, ImageOps, ImageSequence


def prepare(config, root):
    settings = config.get("screensaver", {})
    if not isinstance(settings, dict):
        raise ValueError("screensaver must be an object.")
    fps = settings.get("fps", 60)
    bounce = settings.get("bounce", True)
    images = settings.get("images", {"burger.svg": True})
    if type(fps) is not int or not 1 <= fps <= 120:
        raise ValueError("screensaver.fps must be an integer from 1 to 120.")
    if type(bounce) is not bool:
        raise ValueError("screensaver.bounce must be true or false.")
    if not isinstance(images, dict) or any(
        type(value) is not bool for value in images.values()
    ):
        raise ValueError(
            "screensaver.images must map asset filenames to true or false."
        )
    width, height = config["width"], config["height"]
    size = max(2, min(width, height) // 7 // 2 * 2)
    sprites = []
    assets = (root / "assets").resolve()
    for name, enabled in images.items():
        if not enabled:
            continue
        path = (assets / name).resolve()
        if not path.is_relative_to(assets) or not path.is_file():
            raise ValueError(f"Missing or invalid screensaver asset: {name}")
        if path.suffix.lower() == ".svg":
            data = subprocess.check_output(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-width",
                    str(size),
                    "-height",
                    str(size),
                    "-i",
                    str(path),
                    "-frames:v",
                    "1",
                    "-f",
                    "image2pipe",
                    "-c:v",
                    "png",
                    "-",
                ]
            )
            source = io.BytesIO(data)
        else:
            source = path
        frames, bounds, ends, duration = [], [], [], 0.0
        with Image.open(source) as image:
            for frame in ImageSequence.Iterator(image):
                tile = Image.new("RGBA", (size, size))
                scaled = ImageOps.contain(
                    frame.convert("RGBA"), (size, size), Image.Resampling.LANCZOS
                )
                tile.paste(
                    scaled, ((size - scaled.width) // 2, (size - scaled.height) // 2)
                )
                visible = (
                    tile.getchannel("A")
                    .point([0] * 17 + [255] * 239)
                    .getbbox()
                )
                visible = visible or (0, 0, 0, 0)
                bounds.append(visible)
                frames.append(tile.crop(visible))
                duration += max(10, frame.info.get("duration", 100)) / 1000
                ends.append(duration)
        sprite = {
            "frames": frames,
            "ends": ends,
            "size": size,
            "frame_bounds": bounds,
            "bounds": bounds[0],
        }
        for _ in range(2000):
            x, y = random.uniform(0, width - size), random.uniform(0, height - size)
            if all(
                abs(x - other["x"]) >= size + 4 or abs(y - other["y"]) >= size + 4
                for other in sprites
            ):
                break
        else:
            raise ValueError("Too many screensaver images to place without overlap.")
        sprite.update(
            x=x,
            y=y,
            vx=width * random.uniform(0.12, 0.20) * random.choice((-1, 1)),
            vy=height * random.uniform(0.13, 0.23) * random.choice((-1, 1)),
        )
        sprites.append(sprite)
    return fps, bounce, sprites


def advance(sprites, width, height, dt, bounce):
    # Small steps keep fast objects from passing through each other at low FPS.
    steps = max(1, math.ceil(dt * 240))
    for _ in range(steps):
        for sprite in sprites:
            for axis, limit, offset in (("x", width, 0), ("y", height, 1)):
                velocity = "v" + axis
                sprite[axis] += sprite[velocity] * dt / steps
                lower = -sprite["bounds"][offset]
                upper = limit - sprite["bounds"][offset + 2]
                if sprite[axis] < lower:
                    sprite[axis] = 2 * lower - sprite[axis]
                    sprite[velocity] = abs(sprite[velocity])
                elif sprite[axis] > upper:
                    sprite[axis] = 2 * upper - sprite[axis]
                    sprite[velocity] = -abs(sprite[velocity])
        if not bounce:
            continue
        for index, a in enumerate(sprites):
            for b in sprites[index + 1 :]:
                ax0, ay0, ax1, ay1 = visible_rect(a)
                bx0, by0, bx1, by1 = visible_rect(b)
                overlap_x = min(ax1 - bx0, bx1 - ax0)
                overlap_y = min(ay1 - by0, by1 - ay0)
                if overlap_x <= 0 or overlap_y <= 0:
                    continue
                axis = "x" if overlap_x < overlap_y else "y"
                overlap = min(overlap_x, overlap_y)
                centers = (
                    (ax0 + ax1 - bx0 - bx1) if axis == "x" else (ay0 + ay1 - by0 - by1)
                )
                direction = 1 if centers >= 0 else -1
                velocity = "v" + axis
                a[axis] += direction * overlap / 2
                b[axis] -= direction * overlap / 2
                if direction * (a[velocity] - b[velocity]) < 0:
                    a[velocity], b[velocity] = b[velocity], a[velocity]
        for sprite in sprites:
            left, top, right, bottom = sprite["bounds"]
            sprite["x"] = max(-left, min(width - right, sprite["x"]))
            sprite["y"] = max(-top, min(height - bottom, sprite["y"]))


def visible_rect(sprite):
    left, top, right, bottom = sprite["bounds"]
    return (
        sprite["x"] + left,
        sprite["y"] + top,
        sprite["x"] + right,
        sprite["y"] + bottom,
    )


def frames(sprites, width, height, fps, bounce, seconds=None):
    start = time.monotonic()
    index = 0
    while seconds is None or index < seconds * fps:
        delay = start + index / fps - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        for sprite in sprites:
            elapsed = (index / fps) % sprite["ends"][-1]
            sprite["frame"] = bisect_right(sprite["ends"], elapsed)
            sprite["bounds"] = sprite["frame_bounds"][sprite["frame"]]
        # Resolve motion and any bounds changes from the animation before drawing.
        advance(sprites, width, height, 1 / fps if index else 0, bounce)
        canvas = Image.new("RGB", (width, height), "black")
        for sprite in sprites:
            image = sprite["frames"][sprite["frame"]]
            left, top, _, _ = sprite["bounds"]
            canvas.paste(
                image, (round(sprite["x"]) + left, round(sprite["y"]) + top), image
            )
        yield canvas.tobytes()
        index += 1
