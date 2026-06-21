# flask_storage/processors.py
import io
from PIL import Image


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

        base = Image.open(file_obj).convert('RGBA')
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

        # ── Add shadow ──
        shadow_offset = 2
        shadow_blur = 3
        shadow = Image.new('RGBA', (ww + shadow_blur * 2, wh + shadow_blur * 2), (0, 0, 0, 0))
        
        for i in range(shadow_blur):
            alpha = int(40 * (1 - i / shadow_blur))
            shadow_layer = Image.new('RGBA', (ww, wh), (0, 0, 0, alpha))
            shadow.paste(shadow_layer, (shadow_blur - i + shadow_offset, shadow_blur - i + shadow_offset))

        shadow.paste(wm, (shadow_blur, shadow_blur), mask=wm)
        wm = shadow
        ww, wh = wm.size

        overlay = Image.new('RGBA', base.size, (0, 0, 0, 0))

        if self.position == 'bottom-right':
            coords = (bw - ww - 20, bh - wh - 20)
            overlay.paste(wm, coords, mask=wm)

        elif self.position == 'bottom-left':
            coords = (20, bh - wh - 20)
            overlay.paste(wm, coords, mask=wm)

        elif self.position == 'top-right':
            coords = (bw - ww - 20, 20)
            overlay.paste(wm, coords, mask=wm)

        elif self.position == 'top-left':
            coords = (20, 20)
            overlay.paste(wm, coords, mask=wm)

        elif self.position == 'center':
            coords = ((bw - ww) // 2, (bh - wh) // 2)
            overlay.paste(wm, coords, mask=wm)

        elif self.position == 'tiled':
            for y in range(0, bh, wh):
                for x in range(0, bw, ww):
                    overlay.paste(wm, (x, y), mask=wm)
        
        else:
            # Default to bottom-right if unknown position
            coords = (bw - ww - 20, bh - wh - 20)
            overlay.paste(wm, coords, mask=wm)

        combined = Image.alpha_composite(base, overlay).convert('RGB')

        buffer = io.BytesIO()
        combined.save(buffer, format=self.format)
        buffer.seek(0)
        return buffer