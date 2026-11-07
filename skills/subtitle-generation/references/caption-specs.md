# Caption specifications

## Broadcast vs mobile

| Rule | Broadcast | Mobile |
|---|---|---|
| Characters per line | 42 | 32 |
| Lines per caption | 2 | 2 |
| Reading speed | 20 cps | 17 cps |
| Min duration | 1.0s | 1.0s |
| Max duration | 7.0s | 5.0s |
| Gap | 2 frames (80ms) | 2 frames |

## Vertical short-form styling

- Position: lower third, above the platform UI (not the very bottom)
- Size: 48–64px at 1080x1920
- Bold sans, 4px black outline or a solid box
- Max 3 words per line, 2 lines
- Active word highlighted in a contrasting colour
- **Never centre** — it covers the subject's face

## ASS karaoke style

```ass
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,4,0,2,80,80,200,1
```

`PrimaryColour` is the inactive word (white), `SecondaryColour` is the
highlighted word (yellow). `{\k<centiseconds>}` sets each word's duration.

## Reading-speed checker

```python
def cps(text, start, end):
    return len(text.replace(" ", "")) / max(end - start, 0.001)

if cps(text, start, end) > 17:
    end = start + len(text.replace(" ", "")) / 17
```

## Sidecar vs burned-in

| Format | When |
|---|---|
| Burned-in | Social, short-form, autoplay, accessibility |
| Sidecar `.srt`/`.vtt` | YouTube, courses, anything with a player |
| Both | YouTube — burned-in visuals plus a sidecar for search |

## Font availability

```bash
fc-list | grep -i "dejavu sans"
```

`DejaVu Sans` ships nearly everywhere and is the safe default.
