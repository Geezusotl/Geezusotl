# Profile maintenance

The public profile is the root `README.md`. The About Me wording is manually maintained; the news updater replaces only the region between the two `NEWS` markers.

## Headlines

`newsSources.json` selects four publisher RSS feeds and two headlines per category. `scripts/updateNews.py` uses only the Python standard library. It removes common tracking parameters, rejects unsafe links and XML entities, and retains cached headlines when a source fails. Each category records the last successful fetch. The profile displays the last check and identifies cached results when a fetch fails.

The GitHub Action runs at minute 23 every six hours in UTC, on manual dispatch, or when its code or configuration changes. It needs repository content write access. GitHub can delay scheduled runs and disables schedules after 60 days without repository activity. No external service credentials or paid APIs are needed.

To refresh locally:

```sh
python3 scripts/updateNews.py
```

To reproduce the current rendered headlines without fetching feeds:

```sh
python3 scripts/updateNews.py --cached
```

## Visuals

`assets/about-me.svg` types and erases the same heading in four styles. Font outlines are stored as vector paths, so visitors do not need installed fonts or a third party typing service. `assets/rolling-circle.svg` animates eight dots along straight diameter paths; together, their positions appear to form a rolling circle. Both images contain a reduced motion alternative and use only declarative SVG animation, with no scripts or external dependencies.

`scripts/buildVisuals.py` reproduces the SVGs using fontTools and the font files named in that script. These tools are only needed when rebuilding the images, not when viewing the profile or updating headlines.

The supplied sakura artwork is copied unchanged. Its small display links to the full image. The profile does not alter the account avatar, employment status, or other repositories.
