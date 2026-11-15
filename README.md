# tzbuddy

Time zones for humans: convert a time across cities, see everyone's clock, and find meeting slots that fall inside
everyone's working hours. Python standard library only (`zoneinfo`), so DST is always right.

```console
$ tzbuddy at "tomorrow 9am" beijing london nyc sf
beijing  09:00  ☀  Mon 2026-11-16  UTC+08:00
london   01:00  ☾  Mon 2026-11-16  UTC+00:00
nyc      20:00  ◐  Sun 2026-11-15  UTC-05:00  -1d
sf       17:00  ☀  Sun 2026-11-15  UTC-08:00  -1d

$ tzbuddy meet beijing london berlin --date 2026-11-17
beijing  london   berlin
17:00    09:00    10:00
```

## Install

```bash
pip install git+https://github.com/1252387328/tzbuddy
```

## Usage

```bash
tzbuddy                              # now, here and in UTC
tzbuddy seoul tokyo "new york"       # now in several places
tzbuddy at 15:30 london nyc          # 15:30 London time, elsewhere
tzbuddy at "2026-03-29 02:30" berlin utc
tzbuddy meet sf london --duration 30 --start 8 --end 19
tzbuddy meet tokyo nyc london        # no overlap → shows the least painful hour, exit 1
tzbuddy now beijing --json
```

**Zones** can be IANA names (`Europe/Berlin`, case-insensitive), city names from the tz database (`tokyo`,
`sao paulo`), common aliases (`nyc`, `sf`, `beijing`, `pst`, `cet`) or fixed offsets (`+05:30`, `UTC-8`).
Typos get suggestions: `unknown time zone: tokio (did you mean tokyo?)`.

**Times**: `now`, `15:30`, `3pm`, `12am`, `tomorrow 9am`, `2026-07-04 18:00`.

## Development

```bash
python -m unittest discover -s tests
```
