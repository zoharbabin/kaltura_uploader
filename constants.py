# kaltura_uploader/constants.py

KALTURA_SERVICE_URL = "https://www.kaltura.com/"
KALTURA_API_URL = "https://www.kaltura.com/api_v3/"
KALTURA_CDN_URL_TEMPLATE = (
    "https://cdnapi-ev.kaltura.com/p/{partner_id}/raw/entry_id/{entry_id}/"
    "direct_serve/1/forceproxy/true/{file_name}{extra_query}"
)
