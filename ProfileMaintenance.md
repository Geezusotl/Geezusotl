# Profile maintenance

The public profile is the root `README.md`. The About Me wording is manually maintained and uses GitHub's native Important callout for its purple left border. GitHub also supplies the callout icon and Important label. The news updater replaces only the region between the two `NEWS` markers.

## Headlines

`newsSources.json` selects Technology, AI, Business and markets, and Gaming headlines. Most categories display two items. AI displays three, combining TechCrunch's AI coverage with OpenAI's company announcements. The TechCrunch filter focuses on AI topics and excludes event promotion titles. The combined list favors recent stories and includes another publisher when it has a story within seven days of the newest item. Each headline names its own source.

`scripts/updateNews.py` uses only the Python standard library. It removes common tracking parameters, rejects unsafe links and XML entities, and retains cached headlines if all feeds in a category fail. An available AI feed can keep updating when the other feed fails; individual feed failures appear in the Action logs. Each category records its last successful fetch. The profile displays the last check and identifies cached results when the category cannot refresh.

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

`assets/about-me.svg` types and erases the same white heading in four styles on a transparent background, with no box or typing cursor. Writing takes about 1.74 seconds per style, 15% faster than the original two second typing speed. Erasing takes about 0.87 seconds, twice the writing speed. Each style holds for 1.5 seconds, and the full cycle takes about 18.43 seconds. Font outlines are stored as vector paths, so visitors do not need installed fonts or a third party typing service.

`assets/rolling-circle.svg` animates blue and peach dots along straight diameter paths; together, their positions appear to form a rolling circle. Both images contain a reduced motion alternative and use only declarative SVG animation, with no scripts or external dependencies.

`scripts/buildVisuals.py` reproduces the SVGs using fontTools and the font files named in that script. These tools are only needed when rebuilding the images, not when viewing the profile or updating headlines.

The supplied sakura artwork is copied unchanged. Its small display links to the full image. The profile does not alter the account avatar, employment status, or other repositories.
