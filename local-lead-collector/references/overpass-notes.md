# Overpass and Nominatim notes

## How the search area is chosen

`--place` makes one call to Nominatim, OSM's free geocoder, and takes the top match:

| Nominatim returns | Search used |
|---|---|
| a boundary (relation), e.g. a city or district | the exact boundary (Overpass area). If that finds nothing, one retry with its bounding box |
| an outline (way) | its bounding box |
| a point (node), common for neighbourhoods | a circle of 2000 metres around it |
| anything, when `--radius N` is given | a circle of N metres around the place's centre (ignores the boundary) |

The `area` and `search_mode` lines in the summary show what was matched. If the
match is wrong, add the city and country to the name, or pass `--bbox`.
A bounding box can be read off openstreetmap.org: Export, then "Manually select a different area".

## What a feature becomes

`nwr` in the query means nodes, ways and relations, so a business mapped as a point
or as a building outline is found either way. `out center tags` returns the tags
and a centre point only (no geometry), which keeps responses small.

Fields read: `name:en` or `name`; `website`, `contact:website`, `url`; `phone`,
`contact:phone`, `contact:mobile`; `email`, `contact:email`; `addr:*`; `opening_hours`.
Features without a name are skipped (they are usually unlabelled buildings).

## Usage limits (be a good guest)

- Nominatim: at most 1 request a second and an identifying User-Agent. The script
  makes one request per run.
- Overpass (overpass-api.de): a fair-use public server. Small area queries like
  these are fine; hammering it is not. The script waits at least 5 seconds between
  Overpass calls and backs off on 429 / 504, honouring `Retry-After`. If
  overpass-api.de cannot be reached at all, it tries the community mirror
  overpass.private.coffee. Set `OVERPASS_URL` (comma separated) to use your own.
- Set `LEAD_COLLECTOR_CONTACT` to your own URL or email so server operators can
  reach you; it goes in the User-Agent.

## Troubleshooting

| Symptom | Fix |
|---|---|
| exit 3, `HTTP 429` or `HTTP 504` | The public server is busy. Wait a minute, try a smaller area |
| exit 3, SSL `HANDSHAKE_FAILURE` | Old Python with LibreSSL 2.x (the macOS system Python 3.9 hits this). Use a newer Python, e.g. Homebrew `python3.12` |
| exit 2, place not found | Spell it as on openstreetmap.org, add the country, or use `--bbox` |
| very few rows | OSM coverage varies by country and category. Try a wider area, `--radius`, or related categories (`clinic` next to `dentist`) |
| claude.ai: network errors straight away | Code execution network access is off or limited. Turn on network egress (Settings > Capabilities) or ask the workspace owner to allow the domains in the Skill description |
