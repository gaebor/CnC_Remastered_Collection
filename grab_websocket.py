import sys
import json
from io import BytesIO

import tornado.ioloop
import tornado.web
import tornado.websocket

from PIL import Image


class Application(tornado.web.Application):
    def __init__(self):
        super().__init__([(r"/", MainHandler)])


class MainHandler(tornado.websocket.WebSocketHandler):
    frames = []

    def check_frames():
        expected = range(min(MainHandler.frames), max(MainHandler.frames) + 1)
        if list(expected) != sorted(MainHandler.frames):
            return set(expected) - set(MainHandler.frames)
        else:
            return "check_frames OK!"

    def on_message(self, message):
        text_message, image_data = message[:256], message[256:]

        text_message = text_message[: text_message.index(b'\0')].decode('utf8')
        try:
            text_message = json.loads(text_message)
            if 'frame' in text_message:
                MainHandler.frames.append(text_message['frame'])
            elif text_message == "START":
                MainHandler.frames = []
            elif text_message == "END":
                print(MainHandler.check_frames(), file=sys.stderr)
        except json.decoder.JSONDecodeError as e:
            print(e, sys.stderr)

        if len(image_data) > 0:
            image = Image.open(BytesIO(image_data), formats=['BMP'])
            # if 'frame' in text_message and text_message['frame'] % 100 == 0:
            #     image.show()
        else:
            print(text_message)


def main():
    app = Application()
    app.listen(8888)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.instance().stop()


if __name__ == "__main__":
    main()
