"""
Environment variables configure behavior.

The keys with `os.environ` are required parameters.
The keys with `os.getenv` have defaults and are optional.
"""

import os


# When set to "development", logging level is more verbose and OpenAPI documentation
# becomes available (Optional)
ENV = os.getenv("ENV", "production")

# From the Fotoware auth details, the Client ID
FOTOWARE_CLIENT_ID = os.environ["FOTOWARE_CLIENT_ID"]

# From the Fotoware auth details, the Client secret
FOTOWARE_CLIENT_SECRET = os.environ["FOTOWARE_CLIENT_SECRET"]

# File exports (image only) require a preset, provide its GUID here. (Optional)
# Reference: <https://learn.fotoware.com/Integrations_and_APIs/001_The_FotoWare_API/FotoWare_API_Overview/Export_API#ProgrammaticExportusingtheAPI-GettingthePresetURL>
FOTOWARE_EXPORT_PRESET_GUID = os.getenv("FOTOWARE_EXPORT_PRESET_GUID", None)

# Fotoware host, e.g. <https://tenant.fotoware.cloud>
FOTOWARE_HOST = os.environ["FOTOWARE_HOST"]

# ID of the archive that will be searched. Provide a searchable custom or union archive.
# (Optional)
FOTOWARE_PREFERRED_ARCHIVE = os.getenv("FOTOWARE_PREFERRED_ARCHIVE", "5000")

# Enable additional filtering on retrieved assets. E.g. `"and 601:public"` checks that
# field `601` has the value `public`. (Optional)
# Reference: <https://learn.fotoware.com/On-Premises/FotoWeb/Navigating_and_searching_to_find_your_assets/Searching_in_FotoWeb/001_Searching_for_assets/FotoWare_Search_Expressions_Reference>
FOTOWARE_SEARCH_EXPRESSION_SUFFIX = os.getenv("FOTOWARE_SEARCH_EXPRESSION_SUFFIX", "")

# For the export API, provide a reference to see why the export was made (Optional)
NAME = os.getenv("NAME", "fotoware-http-get-by-id-fastapi")

# Rate-limit in non-development mode the API endpoints
RATE_LIMIT = os.getenv("RATE_LIMIT", "25/minute; 50/hour; 75/day")

# Connection string for the Memcached file cache
MEMCACHED_HOST = os.getenv("MEMCACHED_HOST", "memcached")
