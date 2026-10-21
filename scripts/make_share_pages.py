"""Build link previews for every project card on the homepage.

For each <article class="card" id="..."> in index.html this writes:
  images/og/<id>.png  a 1200x630 preview image (title, date, tags, thumbnail)
  p/<id>.html         a share page with Open Graph tags that sends visitors
                      on to the post, so WhatsApp, LinkedIn, Slack etc. show
                      the right title, description and image
and points the card's "Copy link" button at the share page.
It also renders images/og/home.png for the homepage itself.

Run from the repo root after adding or editing a card:
  python3 scripts/make_share_pages.py
Needs Pillow (pip install pillow). Video thumbnails use their poster frame.
"""
import html
import os
import re

from PIL import Image, ImageDraw, ImageFont, ImageOps

SITE = "https://tiagocabo.github.io/"
W, H = 1200, 630
BG, FG, MUTED, SOFT, LINE = "#ffffff", "#17191c", "#646a73", "#f4f5f7", "#e4e6ea"

FONT_DIRS = ["/usr/share/fonts/opentype/inter", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]


def font(name, size):
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


TITLE = lambda s: font("InterDisplay-SemiBold.otf", s)
BODY = font("Inter-Regular.otf", 26)
SMALL = font("Inter-Medium.otf", 22)
MARK = font("Inter-SemiBold.otf", 20)


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    lines.append(line)
    return lines


def brand(draw, x, y):
    draw.ellipse((x, y, x + 44, y + 44), fill=FG)
    draw.text((x + 22, y + 22), "TC", font=MARK, fill=BG, anchor="mm")
    draw.text((x + 60, y + 22), "Tiago Cabo", font=SMALL, fill=FG, anchor="lm")


def title_block(draw, text, x, y, width, max_lines=4):
    for size in (64, 58, 52, 46):
        fnt = TITLE(size)
        lines = wrap(draw, text, fnt, width)
        if len(lines) <= max_lines:
            break
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=FG)
        y += int(size * 1.14)
    return y


def thumb(img_path, box, cover):
    x0, y0, x1, y1 = box
    panel = Image.new("RGB", (x1 - x0, y1 - y0), SOFT)
    src = Image.open(img_path).convert("RGB")
    if cover:
        fitted = ImageOps.fit(src, panel.size, Image.LANCZOS)
        panel.paste(fitted, (0, 0))
    else:
        pad = 36
        src.thumbnail((panel.width - 2 * pad, panel.height - 2 * pad), Image.LANCZOS)
        panel.paste(src, ((panel.width - src.width) // 2, (panel.height - src.height) // 2))
    mask = Image.new("L", panel.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, *panel.size), radius=18, fill=255)
    return panel, mask


def render_card(card, out):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    brand(d, 64, 60)
    title_block(d, card["title"], 64, 150, 560)
    d.text((64, H - 84), card["meta"], font=SMALL, fill=MUTED)
    panel, mask = thumb(card["img"], (680, 60, W - 60, H - 60), card["cover"])
    im.paste(panel, (680, 60), mask)
    im.save(out, optimize=True)


def render_home(out, thumbs):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    brand(d, 64, 60)
    y = title_block(d, "Machine learning experiments, from search to streaming.", 64, 150, 620, 3)
    for line in wrap(d, "Notebooks, proofs of concept and write-ups.", BODY, 560):
        d.text((64, y + 24), line, font=BODY, fill=MUTED)
        y += 36
    d.text((64, H - 84), "tiagocabo.github.io", font=SMALL, fill=MUTED)
    # Two stacked thumbnails on the right.
    for i, (path, cover) in enumerate(thumbs[:2]):
        top = 60 + i * 265
        panel, mask = thumb(path, (760, top, W - 60, top + 245), cover)
        im.paste(panel, (760, top), mask)
    im.save(out, optimize=True)


SHARE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · Tiago Cabo</title>
  <meta name="description" content="{desc}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Tiago Cabo">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{desc}">
  <meta property="og:url" content="{share}">
  <meta property="og:image" content="{image}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:image:alt" content="{title}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{desc}">
  <meta name="twitter:image" content="{image}">
  <meta http-equiv="refresh" content="0; url={target}">
  <script>location.replace({target_js});</script>
</head>
<body style="font-family: system-ui, sans-serif; padding: 40px">
  <p><a href="{target}">{title}</a></p>
</body>
</html>
"""


def text_of(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def main():
    index = open("index.html", encoding="utf-8").read()
    os.makedirs("images/og", exist_ok=True)
    os.makedirs("p", exist_ok=True)
    cards = []
    for m in re.finditer(r'<article class="card" id="([a-z0-9-]+)">(.*?)</article>', index, re.S):
        slug, body = m.groups()
        img = re.search(r'<img[^>]*src="([^"]+)"', body) or re.search(r'poster="([^"]+)"', body)
        href = re.search(r'<a href="([^"]+)"', body).group(1)
        cards.append({
            "slug": slug,
            "title": text_of(re.search(r"<h2>(.*?)</h2>", body, re.S).group(1)),
            "desc": text_of(re.search(r"<p>(.*?)</p>", body, re.S).group(1)),
            "meta": text_of(re.search(r'<span class="meta">(.*?)</span>', body, re.S).group(1)),
            "img": img.group(1),
            "cover": 'class="cover"' in body,
            # Site articles open directly; external projects land on their card.
            "target": SITE + href if not href.startswith("http") else SITE + "#" + slug,
        })

    for c in cards:
        image = f"images/og/{c['slug']}.png"
        render_card(c, image)
        share = f"{SITE}p/{c['slug']}.html"
        esc = lambda s: html.escape(s, quote=True)
        with open(f"p/{c['slug']}.html", "w", encoding="utf-8") as f:
            f.write(SHARE_PAGE.format(
                title=esc(c["title"]), desc=esc(c["desc"]), target=esc(c["target"]),
                target_js='"' + c["target"] + '"', share=share, image=SITE + image))
        # Point this card's copy button at its share page.
        index = re.sub(
            r'(<article class="card" id="' + c["slug"] + r'">.*?class="copy-link" data-url=")[^"]*',
            lambda m: m.group(1) + share, index, count=1, flags=re.S)

    render_home("images/og/home.png", [(c["img"], c["cover"]) for c in cards if c["cover"]])
    open("index.html", "w", encoding="utf-8").write(index)
    print(f"Built {len(cards)} share pages and preview images.")


if __name__ == "__main__":
    main()
