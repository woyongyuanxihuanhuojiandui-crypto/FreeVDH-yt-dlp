from urllib.parse import urlsplit

from yt_dlp.extractor.bilibili import BiliBiliIE


def standard_media_url(media):
    primary = media.get('baseUrl') or media.get('base_url') or media['url']
    for value in [*(media.get('backupUrl') or media.get('backup_url') or []), primary]:
        url = urlsplit(value)
        if url.scheme == 'https' and url.port in (None, 443):
            return value
    return primary


class _FreeVDHBilibiliIE(BiliBiliIE, plugin_name='freevdh'):
    def extract_formats(self, play_info):
        for kind in ('audio', 'video'):
            for media in play_info.get('dash', {}).get(kind, []):
                media['baseUrl'] = standard_media_url(media)
        return super().extract_formats(play_info)
