from sys import stderr
import json
import time
from os import makedirs

import tornado.ioloop
import tornado.web
import tornado.websocket


class Application(tornado.web.Application):
    def __init__(self):
        super().__init__([(r"/", MainHandler)])


class MainHandler(tornado.websocket.WebSocketHandler):
    messages = []
    record_name = ''

    @staticmethod
    def check_frames():
        frames = [message['frame'] for message in MainHandler.messages if 'frame' in message]
        expected = range(min(frames), max(frames) + 1)
        if list(expected) == sorted(frames):
            return "check_frames OK!"
        else:
            return set(expected) - set(frames)

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
            MainHandler.record_name = f'{hash(time.time()):020}'
            makedirs(MainHandler.record_name)
        elif text_message == "END":
            with open(f'{MainHandler.record_name}/messages.json', 'wt') as f:
                json.dump(MainHandler.messages, f, indent=4)
            print(MainHandler.check_frames(), file=stderr)
            MainHandler.messages = []
        else:
            MainHandler.messages.append(text_message)

        if len(image_data) > 0:
            with open(f'{MainHandler.record_name}/{text_message["frame"]:010}.bmp', 'wb') as f:
                f.write(image_data)
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
