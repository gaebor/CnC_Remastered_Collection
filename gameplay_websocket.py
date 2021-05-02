import json
import argparse
from io import BytesIO

import tornado.ioloop
import tornado.web
import tornado.websocket

import torch
from torchvision.transforms import ToTensor
from PIL import Image

import model


class Application(tornado.web.Application):
    def __init__(self):
        super().__init__([(r"/", MainHandler)])


class MainHandler(tornado.websocket.WebSocketHandler):
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

        if len(image_data) > 0 and 'mouse' in text_message:
            if background_model is not None and gameplay_model is not None:
                image = image_data_to_torch(image_data)
                print(*predict_move(image, *mouse_data_to_torch(text_message['mouse'])))
        else:
            print(text_message)


def image_data_to_torch(image_data):
    return ToTensor()(Image.open(BytesIO(image_data))).to('cuda')[None, :, :, :]


def mouse_data_to_torch(mouse_data):
    cursor = torch.Tensor([[mouse_data['x'], mouse_data['y']]]).to('cuda')
    button = torch.Tensor([mouse_data['button']]).long().to('cuda')
    return cursor, button


def predict_move(image, cursor, button):
    global hidden_state
    predicted_cursor, predicted_button_prob, hidden_state = gameplay_model(
        background_model.embedding(image), cursor, button, hidden_state
    )
    predicted_probs = torch.softmax(predicted_button_prob.to('cpu'), dim=1)[0]
    predicted_button = torch.max(predicted_probs, dim=0)[1].numpy()
    predicted_cursor = predicted_cursor[0].to('cpu').numpy()
    return predicted_cursor, predicted_button


def main():
    app = Application()
    app.listen(8888)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.instance().stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--background', type=str, required=True, help='background model name')
    parser.add_argument('--gameplay', type=str, required=True, help='gameplay model name')
    args = parser.parse_args()

    with torch.no_grad():
        background_model = torch.load(args.background).to('cuda').eval()
        gameplay_model = torch.load(args.gameplay).to('cuda').eval()
        hidden_state = None

        main()
