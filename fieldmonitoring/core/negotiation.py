from rest_framework.negotiation import DefaultContentNegotiation


class _NoFormatOverride:
    URL_FORMAT_OVERRIDE = None


class IgnoreFormatParamNegotiation(DefaultContentNegotiation):
    """For views that read ``?format=csv`` themselves.

    DRF otherwise treats ``?format=`` as a renderer override and answers 404 for "csv". The MIS
    keeps DRF's global override because drf-yasg's pages use ``?format=openapi``.
    """

    settings = _NoFormatOverride()
