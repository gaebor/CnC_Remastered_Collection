import sys
import json
from io import BytesIO

import tornado.ioloop
import tornado.web
import tornado.websocket

import matplotlib.pyplot as plt
import numpy

from PIL import Image

# plt.close(); plt.imshow(255-img); plt.show(block=False)


class Application(tornado.web.Application):
    def __init__(self):
        super().__init__([(r"/", MainHandler)])


class MainHandler(tornado.websocket.WebSocketHandler):
    def on_message(self, message):
        text_message, image_data = message[:256], message[256:]

        text_message = text_message[: text_message.index(b'\0')].decode('utf8')
        try:
            text_message = json.loads(text_message)
        except json.decoder.JSONDecodeError as e:
            print(e, sys.stderr)

        if len(image_data) > 0:
            image = Image.open(BytesIO(image_data), formats=['BMP'])

        print(text_message)


def main():
    MainHandler.fig = plt.figure()
    app = Application()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    main()
