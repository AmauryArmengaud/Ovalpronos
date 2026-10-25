from urllib.parse import urlencode

UTM_KEYS = ('utm_source', 'utm_campaign')


def utm_params(data):
    return {key: data[key][:100] for key in UTM_KEYS if data.get(key)}


def utm_querystring(data):
    return urlencode(utm_params(data))
