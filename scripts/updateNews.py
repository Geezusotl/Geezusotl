"""Refresh publisher headline links in the profile, keeping cached items on failure."""

import argparse
import concurrent.futures
import datetime
import email.utils
import html
import json
import os
import pathlib
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

root = pathlib.Path(__file__).resolve().parents[1]
begin = "<!-- NEWS:START -->"
end = "<!-- NEWS:END -->"
atom = "{http://www.w3.org/2005/Atom}"


def cleanUrl(value):
    parsed = urllib.parse.urlsplit(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
        return None
    tracking = {"fbclid", "gclid", "ref", "referrer", "source", "mc_cid", "mc_eid", "at_medium", "at_campaign", "at_bbc_team", "ns_mchannel"}
    query = [(key, val) for key, val in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
             if not key.lower().startswith("utm_") and key.lower() not in tracking]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), ""))


def parseDate(value):
    if not value:
        return None
    try:
        date = email.utils.parsedate_to_datetime(value)
    except (ValueError, TypeError, OverflowError):
        try:
            date = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    return date.astimezone(datetime.timezone.utc)


def parseFeed(data, now):
    if len(data) > 3000000 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Unsupported feed content")
    document = ET.fromstring(data)
    entries = document.findall("./channel/item")
    isAtom = False
    if not entries:
        entries = document.findall(atom + "entry")
        isAtom = True
    found = []
    seen = set()
    for position, entry in enumerate(entries):
        title = entry.findtext(atom + "title" if isAtom else "title", "")
        title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(title))).strip()
        if isAtom:
            links = entry.findall(atom + "link")
            link = next((el.attrib.get("href", "") for el in links if el.attrib.get("rel", "alternate") == "alternate"), "")
            rawDate = entry.findtext(atom + "published") or entry.findtext(atom + "updated")
        else:
            link = entry.findtext("link", "")
            rawDate = entry.findtext("pubDate") or entry.findtext("{http://purl.org/dc/elements/1.1/}date")
        url = cleanUrl(link)
        date = parseDate(rawDate)
        if not title or not url or url in seen or (date and date > now + datetime.timedelta(hours=1)):
            continue
        seen.add(url)
        found.append({"title": title[:300], "url": url, "published": date.isoformat() if date else None, "position": position})
    found.sort(key=lambda item: (item["published"] or "", -item["position"]), reverse=True)
    for item in found:
        item.pop("position")
    if not found:
        raise ValueError("Feed returned no usable headlines")
    return found


def fetchFeed(feed, now):
    request = urllib.request.Request(feed["url"], headers={"User-Agent": "GeezusotlProfile/1.0 (public RSS headline links)", "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    with urllib.request.urlopen(request, timeout=18) as response:
        data = response.read(3000001)
    items = parseFeed(data, now)
    pattern = feed.get("includeTitlePattern")
    exclusions = [term.casefold() for term in feed.get("excludeTitleTerms", [])]
    return [dict(item, source=feed["source"]) for item in items
            if (not pattern or re.search(pattern, item["title"]))
            and not any(term in item["title"].casefold() for term in exclusions)]


def fetchCategory(category, now, limit):
    feeds = category.get("feeds") or [category]
    items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(feeds)) as pool:
        jobs = {pool.submit(fetchFeed, feed, now): feed for feed in feeds}
        for job in concurrent.futures.as_completed(jobs):
            try:
                items.extend(job.result())
            except Exception as error:
                print(jobs[job]["source"] + ": feed unavailable (" + type(error).__name__ + ")", file=sys.stderr)
    if not items:
        raise ValueError("No configured feed returned usable headlines")
    items.sort(key=lambda item: (item.get("published") or "", item["url"]), reverse=True)
    seen = set()
    unique = []
    for item in items:
        if item["url"] not in seen:
            unique.append(item)
            seen.add(item["url"])
    selected = unique[:limit]
    # Include another publisher when it has recent news, without reviving stale stories.
    if len(feeds) > 1 and limit > 1:
        latest = parseDate(unique[0].get("published")) or now
        for item in unique[limit:]:
            published = parseDate(item.get("published"))
            if item["source"] not in {entry["source"] for entry in selected} and published and published >= latest - datetime.timedelta(days=7):
                selected[-1] = item
                break
    return sorted(selected, key=lambda item: (item.get("published") or "", item["url"]), reverse=True)


def markdownText(value):
    value = html.escape(value, quote=False)
    for char in "\\`*_[]|":
        value = value.replace(char, "\\" + char)
    return value


def renderNews(categories, state):
    lastChecked = parseDate(state["lastChecked"]).strftime("%b %d, %Y at %H:%M UTC")
    rows = [f"<sub>Checked {lastChecked}. Refreshes approximately every six hours.</sub>", ""]
    for category in categories:
        cached = state["categories"].get(category["name"], {})
        rows.extend(["### " + category["name"], ""])
        items = cached.get("items", [])
        if not items:
            rows.append("Headlines are temporarily unavailable.")
        for item in items:
            published = parseDate(item.get("published"))
            label = published.strftime("%b %d, %Y") if published else "Date not supplied"
            safeUrl = item["url"].replace("<", "%3C").replace(">", "%3E").replace("\n", "").replace("\r", "")
            source = item.get("source", category.get("source", "Publisher"))
            rows.append(f"* [{markdownText(item['title'])}](<{safeUrl}>) · {markdownText(source)} · {label}")
        if cached.get("unavailable") and items:
            lastSuccess = parseDate(cached.get("lastSuccess"))
            when = lastSuccess.strftime("%b %d at %H:%M UTC") if lastSuccess else "the previous successful refresh"
            rows.extend(["", f"<sub>Source unavailable at the latest check. Showing headlines saved {when}.</sub>"])
        rows.append("")
    return "\n".join(rows).rstrip()


def replaceNews(readme, content):
    if readme.count(begin) != 1 or readme.count(end) != 1 or readme.index(begin) >= readme.index(end):
        raise ValueError("README must contain exactly one ordered news marker pair")
    return readme.split(begin)[0] + begin + "\n" + content + "\n" + end + readme.split(end)[1]


def atomicWrite(path, content):
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".news-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached", action="store_true", help="Render existing cached headlines without network access")
    args = parser.parse_args()
    config = json.loads((root / "newsSources.json").read_text())
    cachePath = root / "newsCache.json"
    state = json.loads(cachePath.read_text()) if cachePath.exists() else {"categories": {}}
    now = datetime.datetime.now(datetime.timezone.utc)
    if not args.cached:
        state["lastChecked"] = now.isoformat()
        categories = config["categories"]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(fetchCategory, category, now, category.get("limit", config["perCategory"])): category for category in categories}
            for job in concurrent.futures.as_completed(jobs):
                category = jobs[job]
                previous = state["categories"].get(category["name"], {})
                try:
                    state["categories"][category["name"]] = {"items": job.result(), "lastSuccess": now.isoformat(), "unavailable": False}
                    print(category["name"] + ": updated")
                except Exception as error:
                    previous["unavailable"] = True
                    state["categories"][category["name"]] = previous
                    print(category["name"] + ": retained cache (" + type(error).__name__ + ")", file=sys.stderr)
    if "lastChecked" not in state:
        raise ValueError("No cached refresh exists")
    readmePath = root / "README.md"
    updated = replaceNews(readmePath.read_text(), renderNews(config["categories"], state))
    atomicWrite(cachePath, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomicWrite(readmePath, updated)


if __name__ == "__main__":
    main()
