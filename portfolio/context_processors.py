from django.conf import settings

from portfolio.views import SITE


def marketing(request):
    """Expose site settings to all templates."""
    return {
        "site": SITE,
        "site_url": settings.SITE_URL,
    }
