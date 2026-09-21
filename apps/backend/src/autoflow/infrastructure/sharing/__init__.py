"""Persistent network sharing services migrated from WebRPA@5ccb900e.

Source: backend/app/services/{file_share,file_share_page,screen_share}.py.
License: LICENSE.WebRPA.
"""

from .host import NetworkShareHost

__all__ = ["NetworkShareHost"]
