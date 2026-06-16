## 2026-06-08T10:23:45Z
You are worker_2. Your task is to resolve the type safety and default font fallback findings identified in the previous review round for the graphics/watermark modernization in `smm_engine/media/image_handler.py`.

Specifically:
1. Implement a private method in `ImageGenerator`:
```python
    def _parse_color(self, color_val: Any, default: list) -> list:
        """Parses color value from theme configuration (supporting list, tuple, and hex strings) into an RGBA list of 4 integers."""
        if not color_val:
            return default
        if isinstance(color_val, (list, tuple)):
            val = list(color_val)
            if len(val) < 4:
                val = val + [255] * (4 - len(val))
            return val[:4]
        if isinstance(color_val, str):
            color_str = color_val.strip()
            if color_str.startswith("#"):
                hex_val = color_str.lstrip("#")
                if len(hex_val) == 6:
                    r = int(hex_val[0:2], 16)
                    g = int(hex_val[2:4], 16)
                    b = int(hex_val[4:6], 16)
                    return [r, g, b, 255]
                elif len(hex_val) == 8:
                    r = int(hex_val[0:2], 16)
                    g = int(hex_val[2:4], 16)
                    b = int(hex_val[4:6], 16)
                    a = int(hex_val[6:8], 16)
                    return [r, g, b, a]
        return default
```
2. Wrap all colors retrieved from the theme configs using `self._parse_color` to ensure slice and concatenation operations are always safe.
3. Wrap default font fallbacks with try-except blocks:
```python
try:
    coord_font = ImageFont.load_default(size=coord_font_size)
except TypeError:
    coord_font = ImageFont.load_default()
```
Do this for all calls to `ImageFont.load_default()` in `smm_engine/media/image_handler.py`.
4. In `tests/test_media.py`, write a new test `test_image_generator_theme_color_formats(tmp_path)` that explicitly tests passing colors as hex strings and tuples, verifying that no TypeError crashes happen and the cover is still correctly created.
5. Run the pytest suite using the test runner (e.g. `poetry run pytest` or `python -m pytest`) to make sure all unit tests pass completely.
6. Write a completion report and handoff.md in your working directory (d:\SMM\.agents\teamwork_preview_worker_2) and notify me when done.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
