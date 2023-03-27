# fotoware-http-get-by-id-fastapi

Goal: use regular, unauthenticated GET requests to find a Fotoware asset.

## Configuration and usage

- Add .env file with keys that are mentioned in `docker-compose.yaml`.
- `docker compose up -d --build`
- `$ GET localhost:5001/r/fn/filename.jpg`

Use a reverse proxy (e.g., Caddy) to serve this app.

## Documentation

In production mode (`ENV` is not `DEBUG`), there are two endpoints:

- `/r/{field}/{value}` that redirects to:
- `/r/{field}/{value}/filename.extension` where
  - `{field}` is a placeholder a [Fotoware (special) predicate][pred]
  - `{value}` that field's value

This API is also documented on `/docs` and `/redoc`.

Only a single search result MUST be found with the parameters provided.
If there are no results, error 404 is returned.
If there are multiple results, error 404 is returned and the log is updated with a list of matching files.

In debug mode (`ENV=DEBUG`), the `/fotoware/` route proxies the external API and `/j/{field}/{value}` allows searching for a single asset using the same interface, but returns a JSON representation of the asset.

[pred]: https://learn.fotoware.com/FotoWare_SaaS/Navigating_and_searching_to_find_your_assets/Searching_in_FotoWare/001_Searching_for_assets/FotoWare_Search_Expressions_Reference

## Known issues

Using UNION archives, the same file may appear with the same attributes and filename, yet in different archives.
The API returns for each asset a `physicalFileId`, but this field cannot be searched for.
