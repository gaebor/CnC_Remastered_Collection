from sys import stderr
import json
import time
import zipfile

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
            MainHandler.record_name = f'{hash(time.time()):020}.zip'
            with zipfile.ZipFile(MainHandler.record_name, 'w'):
                pass
        elif text_message == "END":
            with zipfile.ZipFile(MainHandler.record_name, 'a') as f:
                f.writestr('messages.json', json.dumps(MainHandler.messages, indent=4))
            print(MainHandler.check_frames(), file=stderr)
            MainHandler.messages = []
        else:
            MainHandler.messages.append(text_message)

        if len(image_data) > 0:
            with zipfile.ZipFile(
                MainHandler.record_name, 'a', compression=zipfile.ZIP_DEFLATED, compresslevel=1
            ) as f:
                f.writestr(f'{text_message["frame"]:010}.bmp', image_data)
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
