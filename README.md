# Meal calendar

This week's dinners as a calendar feed plus a recipe page for each one.

- Feed to subscribe to: https://bradfordholden.github.io/meal-calendar/meals.ics
- This week: https://bradfordholden.github.io/meal-calendar/

## How it updates
The weekly grocery routine writes `data/weeks/<week start>.json` (and a `data/recipes/<slug>.json` for any new recipe), runs `python3 build.py`, and pushes. Generated files: `meals.ics`, `index.html`, `r/<slug>/index.html`.

Recipe photos from other sites are shown from those sites, not copied here. Our own photos go in `r/<slug>/` and the recipe's `photo.url` is just the file name.
