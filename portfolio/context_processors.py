from django.conf import settings

from portfolio.views import SITE


def marketing(request):
    """Expose site + marketing settings to all templates."""
    return {
        "site": SITE,
        "site_url": settings.SITE_URL,
        "meta_pixel_id": settings.META_PIXEL_ID,
    }
