# flask_storage/processors.py
import io
from PIL import Image, ImageFilter


class WatermarkProcessor:
    """
    Apply a watermark image onto an uploaded file stream.

    Args:
        path (str):      Filesystem path to the watermark image.
        opacity (float): Watermark opacity in the range 0.0–1.0. Default 0.5.
        position (str):  One of 'center', 'bottom-right', or 'tiled'.
                         Default 'center'.
        format (str):    Output format passed to PIL (e.g. 'JPEG', 'PNG').
                         Default 'JPEG'.
    """

    def __init__(self, path, opacity=0.5, position='center', format='JPEG', size=15):
        self.path     = path
        self.opacity  = max(0.0, min(100.0, opacity))   # handle 0-100 or 0.0-1.0
        self.position = position
        self.format   = format
        self.size     = size # Percentage of base image width

    def apply(self, file_obj):
        """
        Composite the watermark onto *file_obj* and return a new BytesIO stream.
        """
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)

        image = Image.open(file_obj)
        # Flattening an animation into a single frame would silently destroy it.
        if getattr(image, 'is_animated', False):
            file_obj.seek(0)
            return file_obj

        base = image.convert('RGBA')
        wm   = Image.open(self.path).convert('RGBA')
        
        bw, bh = base.size
        
        # ── Resize Watermark ──
        # Use dynamic size from config (percentage of base image width)
        target_ww = int(bw * (self.size / 100.0))
        if target_ww < 50: target_ww = 50 # Minimum size
        
        # Maintain aspect ratio
        w_orig, h_orig = wm.size
        target_wh = int(target_ww * (h_orig / w_orig))
        
        wm = wm.resize((target_ww, target_wh), Image.Resampling.LANCZOS)
        ww, wh = wm.size

        # ── Scale Opacity ──
        r, g, b, a = wm.split()
        # If opacity is passed as 0-100, convert to 0-1
        op = self.opacity / 100.0 if self.opacity > 1.0 else self.opacity
        a = a.point(lambda p: int(p * op))
        wm = Image.merge('RGBA', (r, g, b, a))

        # ── Add soft shadow ──
        # A blurred silhouette keeps the mark legible on bright photos; the
        # blur radius scales with the watermark so small images stay sharp.
        blur = max(2, int(ww * 0.015))
        margin = blur * 2
        shadow = Image.new('RGBA', (ww + margin * 2, wh + margin * 2), (0, 0, 0, 0))

        silhouette = Image.new('RGBA', (ww, wh), (0, 0, 0, 0))
        silhouette.putalpha(wm.getchannel('A').point(lambda p: int(p * 0.6)))
        shadow.alpha_composite(silhouette, (margin + 2, margin + 2))
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
        shadow.alpha_composite(wm, (margin, margin))
        wm = shadow
        ww, wh = wm.size

        overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))

        if self.position == 'bottom-right':
            coords = (bw - ww - 20, bh - wh - 20)
            overlay.alpha_composite(wm, coords)

        elif self.position == 'bottom-left':
            coords = (20, bh - wh - 20)
            overlay.alpha_composite(wm, coords)

        elif self.position == 'top-right':
            coords = (bw - ww - 20, 20)
            overlay.alpha_composite(wm, coords)

        elif self.position == 'top-left':
            coords = (20, 20)
            overlay.alpha_composite(wm, coords)

        elif self.position == 'center':
            coords = ((bw - ww) // 2, (bh - wh) // 2)
            overlay.alpha_composite(wm, coords)

        elif self.position == 'tiled':
            for y in range(0, bh, wh):
                for x in range(0, bw, ww):
                    tile = wm.crop((0, 0, min(ww, bw - x), min(wh, bh - y)))
                    overlay.alpha_composite(tile, (x, y))
        
        else:
            # Default to bottom-right if unknown position
            coords = (bw - ww - 20, bh - wh - 20)
            overlay.alpha_composite(wm, coords)

        combined = Image.alpha_composite(base, overlay)
        # Formats without alpha (JPEG) flatten transparent pixels to black;
        # composite onto white first so PNG/WebP cut-outs stay clean.
        white = Image.new('RGBA', combined.size, (255, 255, 255, 255))
        combined = Image.alpha_composite(white, combined).convert('RGB')

        buffer = io.BytesIO()
        combined.save(buffer, format=self.format)
        buffer.seek(0)
        return buffer