# fotoware-http-get-by-id-fastapi

Goal: use regular, unauthenticated GET requests to retrieve a Fotoware asset.

Complication: there is currently no single, archive-independent identifier that can be queries for.
There is an archive-dependent file path and there is a `physicalFileId` that however cannot be queried for.

## Configuration and usage

- Provide environment variables ([required and optional](app/config.py))
- `$ docker compose up -d --build`
- `$ curl -X GET http://localhost:5001/id/fn/filename.jpg`

Use a reverse proxy (e.g., Caddy) to serve this app.

## Documentation

In production mode (`ENV` is not `development`), there are two endpoints:

- `/id/{field}/{value}` that redirects to:
- `/doc/{field}/{value}/filename.extension` where
  - `{field}` is a placeholder a [Fotoware (special) predicate][pred]
  - `{value}` that field's value.
  - The `filename.extension` is not checked and may be used to rename a download.

This API is also documented on `/docs` and `/redoc`.

Only a single search result MUST be found with the parameters provided.
If there are no results, error 404 is returned.
If there are multiple results, error 404 is returned and the log is updated with a list of matching files.

In development mode (`ENV=development`), the `/fotoware/` route proxies the complete external API and `/json/{field}/{value}[/{filename}]` allows searching for a single asset using the same interface, but returns a JSON representation of the asset.

[pred]: https://learn.fotoware.com/FotoWare_SaaS/Navigating_and_searching_to_find_your_assets/Searching_in_FotoWare/001_Searching_for_assets/FotoWare_Search_Expressions_Reference

## Known issues

Using UNION archives, the same file may appear with the same attributes and filename, yet in different archives.
The API returns for each asset a `physicalFileId`, but this field cannot be searched for.
