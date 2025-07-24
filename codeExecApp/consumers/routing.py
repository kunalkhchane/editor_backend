from django.urls import re_path
from . import code_consumer

websocket_urlpatterns = [
    re_path(r'ws/run/$', code_consumer.CodeConsumer.as_asgi()),
]