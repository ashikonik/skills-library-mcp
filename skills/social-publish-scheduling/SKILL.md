---
name: social-publish-scheduling
description: Plan, schedule, and publish social media content across platforms — content calendars, per-platform formatting, hashtag and metadata sets, UTM tagging, and cross-posting to Mastodon, Bluesky, LinkedIn, Reddit, and self-hosted feeds via open APIs. Use when the user wants a posting schedule, a content calendar, to publish across platforms, or to repurpose one piece of content per network.
metadata:
  promptSignals:
    phrases:
      - social media schedule
      - content calendar
      - publish to social media
      - cross post
      - post to mastodon
      - post to bluesky
      - schedule posts
      - repurpose content per platform
      - hashtag set
---

# Social Publish Scheduling

Scheduling is mostly *formatting decisions made once*. The hard part is not
the API call — it is that each platform rewards a different shape of the same
idea.

## The per-platform adaptation matrix

| Platform | Optimal length | Media | Link in post? | Hook position |
|---|---|---|---|---|
| Bluesky | 280 chars | 4 images | Yes | First line |
| Mastodon | 500 chars | Video/GIF | Yes | First line |
| LinkedIn | 1200–2000 chars | Document/image | Yes | First 2 lines, then "see more" |
| Reddit | Title ≤ 300 chars | Link/image | Post link | Title only |
| Instagram | Caption 2200, hook in image | Reel/carousel | No | On the image |
| TikTok / Reels | 0 caption | Video | No | First 1.5 seconds of video |
| YouTube Shorts | ≤ 500 chars | Video | No | First frame |

**Two universal rules:**

1. **The first line is the hook.** On every text platform the rest is hidden
   behind "see more". The first line must land without context.
2. **Never paste the same text twice.** Cross-posting identical copy is the
   fastest way to look like a bot.

## Content calendar

```python
from dataclasses import dataclass, field
from datetime import date, datetime, time

@dataclass
class Post:
    date: date
    time: time
    platform: str
    pillar: str            # content pillar: education / proof / story / offer
    hook: str              # first line, the only part guaranteed to be seen
    body: str = ""
    media: list[str] = field(default_factory=list)
    cta: str = ""
    hashtags: list[str] = field(default_factory=list)
    status: str = "draft"  # draft / approved / scheduled / published
    published_at: datetime | None = None

CALENDAR = [
    Post(date(2026, 11, 5), time(9, 0), "bluesky", "education",
         "Most teams measure reach. The ones that grow measure saves.",
         body="Saves signal intent... here's how to read them.",
         hashtags=["#marketing", "#growth"]),
]
```

A real calendar is one sheet with these columns. The pillar rotation is what
keeps a feed from being seven days of product shots:

| Pillar | Share | Purpose |
|---|---|---|
| Education | 40% | Teach something useful |
| Proof | 20% | Results, case studies, screenshots |
| Story | 20% | Behind the scenes, founder narrative |
| Offer | 20% | The ask |

## Per-platform copy generation

```python
import re

BLUESKY_LIMIT = 300
LINK_RE = re.compile(r"https?://\S+")
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#\w+")

def strip_meta(text: str) -> str:
    """Remove links, mentions and hashtags — they cost characters differently per platform."""
    text = LINK_RE.sub("", text)
    text = MENTION_RE.sub("", text)
    text = HASHTAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()

def fit_links(text: str, limit: int, reserved: int = 30) -> str:
    """Bluesky and Mastodon count a link as a fixed number of characters."""
    if len(text) + reserved <= limit:
        return text
    return text[: limit - reserved - 1].rsplit(" ", 1)[0] + "…"

def to_bluesky(post) -> dict:
    body = strip_meta(post.body)
    links = LINK_RE.findall(post.body)
    text = f"{post.hook}\n\n{body}".strip()
    if links:
        text = fit_links(text, BLUESKY_LIMIT)
    return {
        "text": text,
        "facets": [],          # mention/facet objects, built from MENTION_RE matches
        "langs": ["en"],
        "post": post.body,     # keep the link out of the truncation
    }

def to_linkedin(post) -> dict:
    # LinkedIn: hook first, blank line, then detail, then a soft CTA
    parts = [post.hook, "", post.body]
    if post.cta:
        parts += ["", post.cta]
    return {"text": "\n".join(parts).strip()}

def to_mastodon(post) -> dict:
    # Mastodon: 500 chars, tags as separate hashtags field
    text = f"{post.hook}\n\n{post.body}".strip()
    if len(text) > 500:
        text = fit_links(text, 500)
    return {
        "status": text,
        "tags": [h.lstrip("#") for h in post.hashtags],
        "visibility": "public",
        "language": "en",
    }
```

**Do not truncate blindly.** Cutting a post at 280 characters usually removes
the point. Rewrite to fit instead — drop the setup sentence, keep the claim
and the CTA.

## Hashtag strategy

- **Bluesky/Mastodon**: 0–3 hashtags, in a separate `tags` field where
  supported. Hashtags in the body break links on Mastodon.
- **Instagram/TikTok**: 3–8, in the caption; TikTok effectively ignores them now.
- **LinkedIn**: 3–5, max. More looks desperate.
- **Reddit**: none in the body. Reddit has per-subreddit rules; read them.

```python
def hashtag_set(post, platform: str) -> list[str]:
    if platform in ("bluesky", "mastodon"):
        return post.hashtags[:3]
    if platform in ("instagram", "tiktok"):
        return post.hashtags[:8]
    if platform == "linkedin":
        return post.hashtags[:5]
    return []
```

## UTM tagging

Every link needs attribution. Build it once, at publish time.

```python
from urllib.parse import urlencode

def utm(url: str, source: str, medium: str, campaign: str,
        content: str = "", term: str = "") -> str:
    params = {
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign,
    }
    if content: params["utm_content"] = content
    if term:    params["utm_term"] = term
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{urlencode(params)}"
```

```python
utm("https://example.com/post",
    source="bluesky", medium="social",
    campaign="2026-11-launch",
    content="hook-01")   # distinguishes two posts in the same campaign
```

`utm_content` is what separates two posts sharing one campaign. Without it,
analytics cannot tell which creative worked.

## Publishing via open APIs

### Mastodon

```bash
# create an app once
curl -X POST https://mastodon.social/api/v1/apps \
  -d client_name=my-content-bot \
  -d redirect_uri=urn:ietf:wg:oauth:2.0:oob \
  -d scopes="read write" \
  -d client_id="$CLIENT_ID" -d client_secret="$CLIENT_SECRET"
```

```python
import requests

def post_mastodon(base_url: str, token: str, text: str,
                  tags: list[str] | None = None) -> str:
    r = requests.post(f"{base_url}/api/v1/statuses",
                      headers={"Authorization": f"Bearer {token}"},
                      json={"status": text, "tags": tags or [],
                            "visibility": "public"},
                      timeout=30)
    r.raise_for_status()
    return r.json()["url"]
```

### Bluesky

```python
def post_bluesky(service: str, handle: str, password: str,
                  text: str) -> str:
    import requests
    s = requests.Session()
    r = s.post(f"https://{service}/xrpc/com.atproto.server.createSession",
               json={"identifier": handle, "password": password}, timeout=30)
    r.raise_for_status()
    sess = r.json()
    r = s.post(f"https://{service}/xrpc/com.atproto.repo.createRecord",
               headers={"Authorization": f"Bearer {sess['accessJwt']}"},
               json={"repo": sess["did"], "collection": "app.bsky.feed.post",
                     "record": {"$type": "app.bsky.feed.post",
                                "text": text, "createdAt": datetime.now(timezone.utc).isoformat()}},
               timeout=30)
    r.raise_for_status()
    uri = r.json()["uri"]
    return f"https://bsky.app/profile/{handle}/post/{uri.split('/')[-1]}"
```

### Reddit

```bash
curl -H "Authorization: bearer $REDDIT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"sr":"r/example","title":"Title","kind":"self","text":"Body","api_type":"json"}' \
  -A "my-bot/0.1" \
  https://oauth.reddit.com/api/submit
```

**Read each subreddit's rules before posting.** Most ban self-promotion
outright, and account-age/karma filters will silently drop a new account.

### LinkedIn

LinkedIn has no fully open posting API — the API is restricted to approved
partners and app review. Plan the content and publish manually, or use an
approved integration. Do not attempt unauthenticated posting.

## Scheduling

Cron is enough for a single platform; a small queue file handles the rest.

```python
import json, os, time
from datetime import datetime

QUEUE = "publish_queue.json"

def load_queue():
    if os.path.exists(QUEUE):
        return json.load(open(QUEUE))
    return []

def due(queue, now=None):
    now = now or datetime.now()
    return [p for p in queue if p["status"] == "scheduled"
            and datetime.fromisoformat(p["scheduled_at"]) <= now]
```

A cron entry that runs the publisher every 15 minutes:

```cron
*/15 * * * * cd /srv/content && python publish.py >> logs/publish.log 2>&1
```

**Idempotency matters** — a retry after a partial failure must not double-post.
Record the platform's returned URL as the idempotency key and skip any post
that already has one.

## Common failures

**The post is invisible** — the hook is weak, or the platform buried it. On
LinkedIn the first two lines are all most people see.

**A link preview takes over the post** — add a trailing link to a comment if
the platform allows it, or post as "self" on Reddit.

**Scheduling fired twice** — no idempotency check. Store the returned URL and
check it before posting.

**Character limits differ from what you counted** — Bluesky counts links as 23
characters; Mastodon counts them as 23 too but URLs are shortened. Test against
the real API, not a local count.

**Account rate-limited** — new accounts hit strict daily caps. Space posts
out; expect the first 20 posts to be reviewed.

**Cross-posting feels automated** — rewrite the hook per platform. Same idea,
different opening line.

**The wrong timezone** — store timestamps in UTC, convert for display. Timezone
mistakes are the most common scheduling bug.

**A hashtag broke the link on Mastodon** — Mastodon only links hashtags in the
`tags` field. Keep them out of the body.

**The post was flagged by a filter** — some platforms filter outbound links in
posts by brand-new accounts. Post text-only first, build history, then link.

## Reference tools

Other open-source text tools worth knowing, each over 1,000
GitHub stars — see `references/text-reference-tools.md`.

## Related skills

`crosspost` · `content-engine` · `seo` ·
`shorts-reels-pipeline` · `long-to-short-repurpose` · `thumbnail-generator`
