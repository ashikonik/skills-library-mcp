# Stock media APIs

## Pexels

```python
requests.get("https://api.pexels.com/videos/search",
    headers={"Authorization": PEXELS_KEY},
    params={"query": "...", "per_page": 30, "orientation": "landscape"})
```

Response shape:

```json
{"videos": [{"id": 123, "duration": 12, "url": "...",
             "video_files": [{"link": "...", "width": 1920, "height": 1080}],
             "user": {"name": "..."}}]}
```

Pick the smallest file at or above your target resolution.

## Unsplash

```python
requests.get("https://api.unsplash.com/search/photos",
    headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
    params={"query": "..."})
```

`urls.raw` for full resolution; `urls.regular` (1080px) is usually enough.

## Wikimedia Commons

```python
requests.get("https://commons.wikimedia.org/w/api.php", params={
    "action": "query", "format": "json",
    "generator": "search", "gsrsearch": "query",
    "gsrnamespace": 6, "gsrlimit": 20,
    "prop": "imageinfo",
    "iiprop": "url|extmetadata|size",
})
```

Read `extmetadata.LicenseShortName` for every file — the licence is per
file, not per-collection.

## Pixabay

```python
requests.get("https://pixabay.com/api/videos/", params={
    "key": PIXABAY_KEY, "q": "query", "per_page": 30})
```

## Internet Archive

```python
requests.get("https://archive.org/advancedsearch.php", params={
    "q": "query", "fl[]": ["identifier", "title", "licenseurl"],
    "rows": 20, "output": "json"})
```

Then `https://archive.org/metadata/{identifier}` for the file list.

## Licences

| Source | Attribution required | Commercial use |
|---|---|---|
| Pexels | No | Yes |
| Unsplash | No (appreciated) | Yes |
| Pixabay | No | Yes |
| Wikimedia Commons | Depends — often CC BY-SA | Depends |
| Internet Archive | Depends — often none | Depends |
| Openverse | Filter by licence | Filter by licence |
