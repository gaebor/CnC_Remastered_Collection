from sys import stderr
import json
import time
from os import makedirs
from multiprocessing import Pool
from io import BytesIO
from random import sample

import tornado.ioloop
import tornado.web
import tornado.websocket

from PIL import Image


def save_image_data(image_data, filename):
    Image.open(BytesIO(image_data), formats=['BMP']).save(
        filename + ".jpg", format="JPEG", quality=95
    )


class Application(tornado.web.Application):
    def __init__(self):
        super().__init__([(r"/", MainHandler)])


class MainHandler(tornado.websocket.WebSocketHandler):
    messages = []
    record_name = ''
    async_results = []

    @classmethod
    def cleanup(cls):
        while len(cls.async_results) > 0:
            cls.async_results.pop().get()

    def on_message(self, message):
        text_message, image_data = message[:256], message[256:]
        text_message = text_message[: text_message.index(b'\0')]
        try:
            text_message = text_message.decode('utf8')
        except UnicodeDecodeError as e:
            print(e, stderr)
            text_message = text_message.decode('latin1')

        try:
            text_message = json.loads(text_message)
        except json.decoder.JSONDecodeError as e:
            print(e, stderr)

        if text_message == "START":
            MainHandler.messages = []
            MainHandler.cleanup()
            MainHandler.record_name = f'{hash(time.time()):020}'
            makedirs(MainHandler.record_name)
        elif text_message == "END":
            with open(f'{MainHandler.record_name}/messages.json', 'wt') as f:
                json.dump(MainHandler.messages, f, indent=4)
            MainHandler.messages = []
            MainHandler.cleanup()
            print_team_colors()
        else:
            MainHandler.messages.append(text_message)

        if len(image_data) > 0:
            MainHandler.async_results.append(
                pool.apply_async(
                    save_image_data,
                    (image_data, f'{MainHandler.record_name}/{text_message["frame"]:010}'),
                )
            )
        else:
            print(text_message)


def print_team_colors():
    print("Suggested colors:", sample(['GDI', 'Blue', 'Red', 'Green', 'Orange', 'Teal'], 2))


def main():
    print_team_colors()
    app = Application()
    app.listen(8888)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        MainHandler.cleanup()
        tornado.ioloop.IOLoop.instance().stop()


if __name__ == "__main__":
    with Pool() as pool:
        main()
