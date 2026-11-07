---
name: stock-media-sourcing
description: Find and download royalty-free stock photos, video, and music for content production — Pexels, Pixabay, Unsplash, Wikimedia Commons, and Internet Archive — with API usage, licence verification, search query strategies, and attribution requirements. Use when the user needs B-roll, background footage, stock images, or free music for a video or article.
metadata:
  promptSignals:
    phrases:
      - stock footage
      - stock photos
      - find b-roll
      - pexels api
      - unsplash api
      - free stock video
      - royalty free music
      - wikimedia commons
      - download stock media
      - background footage
---

# Stock Media Sourcing

Finding and downloading footage, images, and music that you can actually publish.

## Sources

| Source | Type | API key | Licence |
|---|---|---|---|
| **Pexels** | Video + Photos + Music | Free | Pexels Licence — free, no attribution required |
| **Pixabay** | Video + Photos + Music | Free | Pixabay Content Licence |
| **Unsplash** | Photos only | Free | Unsplash Licence |
| **Wikimedia Commons** | Images, video, audio | None | Per-file, often CC BY / CC0 / PD |
| **Internet Archive** | Video + audio | None | Per-item, mostly public domain |
| **Openverse** | Aggregator across CC sources | Optional | Per-source |

**Pexels is the default for video B-roll.** Its search quality for "what a shot
of X looks like" is better than anything else free.

**Openverse is unreliable right now.** Its `/v1/images/` endpoint returns
HTTP 504 (gateway timeout) while `/v1/audio/` still responds — it is an
upstream outage, not a bug in your request. If a search returns 504, switch
to Wikimedia Commons rather than debugging the parameters.

## Pexels API

```bash
export PEXELS_API_KEY=your_key
```

```bash
# search videos
curl -s "https://api.pexels.com/videos/search?query=coffee%20pour&per_page=15&orientation=vertical" \
  -H "Authorization: $PEXELS_API_KEY"

# search photos
curl -s "https://api.pexels.com/v1/search?query=mountain%20landscape&per_page=15" \
  -H "Authorization: $PEXELS_API_KEY"
```

```python
import os, requests

KEY = os.environ["PEXELS_API_KEY"]
BASE = "https://api.pexels.com"

def search_videos(query, orientation="vertical", per_page=15):
    r = requests.get(f"{BASE}/videos/search",
                     params={"query": query, "per_page": per_page,
                             "orientation": orientation},
                     headers={"Authorization": KEY})
    r.raise_for_status()
    return r.json()["videos"]

def download(video, out_dir="footage", min_duration=5, max_duration=60):
    """Pick the best mp4 file from a Pexels video object and download it."""
    os.makedirs(out_dir, exist_ok=True)
    if not (min_duration <= video.get("duration", 0) <= max_duration):
        return None
    # prefer a small-file mp4 over the original
    files = sorted(video["video_files"], key=lambda f: f["file_size"])
    chosen = next((f for f in files if f["quality"] == "hd" and f["file_type"] == "video/mp4"),
                   files[0])
    dest = os.path.join(out_dir, f"{video['id']}.mp4")
    with requests.get(chosen["link"], stream=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    return dest
```

`orientation=vertical` is directly supported and saves a crop step.

## Unsplash API

```bash
export UNSPLASH_ACCESS_KEY=your_key
```

```bash
curl -s "https://api.unsplash.com/search/photos?query=architecture&per_page=20&orientation=landscape" \
  -H "Authorization: Client-ID $UNSPLASH_ACCESS_KEY"
```

Note the header is `Client-ID`, not `Authorization` like Pexels.

## Wikimedia Commons — no key needed

```bash
curl -s "https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrsearch=filetype:video%20lighthouse&gsrnamespace=6&gsrlimit=10&prop=imageinfo&iiprop=url|extmetadata"
```

```python
import requests

def commons_files(query, limit=20):
    params = {
        "action": "query", "format": "json",
        "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|extmetadata",
    }
    data = requests.get(
        "https://commons.wikimedia.org/w/api.php", params=params).json()
    out = []
    for page in data.get("query", {}).get("pages", {}).values():
        info = page.get("imageinfo", [{}])[0]
        meta = info.get("extmetadata", {})
        out.append({
            "title": page.get("title"),
            "url": info.get("url"),
            "license": meta.get("LicenseShortName", {}).get("value"),
            "artist": meta.get("Artist", {}).get("value"),
        })
    return out
```

**Wikimedia licences vary per file.** Always read `extmetadata.LicenseShortName`
and `Artist`. CC BY requires attribution; CC0 and public domain do not.

## Internet Archive

```bash
curl -s "https://archive.org/advancedsearch.php?q=subject:%22silent+film%22+AND+mediatype:movies&fl%5B%5D=identifier&fl%5B%5D=title&rows=20&output=json"
```

Public domain films and pre-1930 stock footage live here. Watch out for
`mediatype:audio` for old music and sound effects.

## Search query strategy

Stock sites index by **literal visual description**, not by concept.

| Instead of | Search |
|---|---|
| "focus" | "shallow depth of field" |
| "premium" | "studio lighting product photo" |
| "cinematic city" | "city skyline dusk timelapse" |
| "business meeting" | "office team meeting laptop" |
| "emotional" | "person looking out window rainy day" |

**Include the camera framing** — stock footage is heavily searched by shot type:
`aerial`, `close up`, `wide shot`, `tracking shot`, `drone`, `slow motion`,
`timelapse`, `handheld`.

**Include the direction and time of day** — `walking left to right`,
`handheld`, `golden hour`, `overcast`.

## Choosing clips

- **Shoot length** — 5+ seconds minimum. You will trim.
- **Resolution** — 1080p minimum, 4K if you will upscale.
- **Motion direction** — match across cuts. A subject moving left in shot A
  should be moving left in shot B.
- **Avoid** — shots with visible logos, plates, or faces you cannot licence.
  Stock licences cover the clip, not necessarily every face in it.

## Music

Pexels and Pixabay both have free music. For longer or higher quality:

| Source | Notes |
|---|---|
| [incompetech](https://incompetech.com) | CC BY, well-known library |
| [Free Music Archive](https://freemusicarchive.org) | Per-track CC licence |
| [Jamendo](https://www.jamendo.com) | Free with attribution for some tracks |
| [YouTube Audio Library](https://studio.youtube.com) | Free, no attribution, YouTube only |
| [Pixabay Music](https://pixabay.com/music/) | No attribution, broad use |

Check the licence on **every track**. "Free" usually still means "free with
attribution" or "non-commercial only".

## Attribution

Even when not required, record it. Keep a manifest:

```json
{
  "clips": [
    {
      "file": "footage/12345.mp4",
      "source": "pexels",
      "id": 12345,
      "url": "https://www.pexels.com/video/...",
      "creator": "Jane Doe",
      "license": "Pexels License",
      "downloaded": "2026-11-05"
    }
  ]
}
```

For CC BY content, the attribution goes in the video description or the credits
card: *"Footage by Jane Doe, CC BY 4.0"*.

## Common failures

**Downloaded clip is the wrong aspect** — request `orientation=vertical` rather
than cropping later.

**Search returns nothing** — the query is too conceptual. Describe what is
literally in frame.

**Footage does not match the edit** — shot length too short, or the motion
direction is wrong. Pull 3 candidates and pick.

**Licence conflict** — a stock clip contains a recognisable trademark or a
person's face. Stock licences cover the photographer's copyright, not third-party
rights.

**Music claim on YouTube** — the track was from a Content ID registry. Use
Pexels/Pixabay music, or an explicit CC BY track, and keep the licence in your
records.

## Related skills

`shorts-reels-pipeline` · `long-to-short-repurpose` · `music-generation` ·
`thumbnail-generator` · `subtitle-generation`
