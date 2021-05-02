from sys import stderr
import json
import argparse
from io import BytesIO
import time
from contextlib import nullcontext

import tornado.ioloop
import tornado.web
import tornado.websocket

import torch
from torchvision.transforms import ToTensor
from PIL import Image
from torch.utils.data import DataLoader, TensorDataset

import cnc_ai.model
from cnc_ai.common import retrieve

from winapi import MoveMouse


class Application(tornado.web.Application):
    def __init__(self):
        super().__init__([(r"/", MainHandler)])


def torch_safe_load(filename, constructor):
    try:
        return torch.load(filename)
    except FileNotFoundError:
        return constructor()


class Learner:
    def __init__(self, args):
        self.args = args
        self.background_model = torch_safe_load(
            args.background,
            lambda: cnc_ai.model.Predictor(
                cnc_ai.model.ImageEmbedding(),
                cnc_ai.model.Generator(activation=torch.nn.Sigmoid()),
            ),
        ).to(args.device)
        self.gameplay_model = torch_safe_load(args.gameplay, cnc_ai.model.GamePlay).to(args.device)

        if args.train == 0:
            self.background_model.eval()
            self.gameplay_model.eval()
        elif args.train == 1:
            self.gameplay_model.eval()

        self.background_optimizer = torch.optim.RMSprop(
            self.background_model.parameters(), lr=args.lr, momentum=0, alpha=0.5
        )
        self.gameplay_optimizer = torch.optim.RMSprop(
            self.gameplay_model.parameters(), lr=args.lr, momentum=0, alpha=0.5
        )

        self.restart()

    def step(self, image_data, text_message):
        current_time = time.time()
        if len(image_data) > 0 and 'mouse' in text_message and 'frame' in text_message:
            self.advance_background_model(
                image_data,
                text_message,
                gradient_step=bool(self.args.train & 1),
                make_move=self.args.move,
            )
            print(
                "\r{:8.3f}ms/{:8.3f}ms".format(
                    1000 * (time.time() - current_time), 1000 * (current_time - self.previous_time)
                ),
                file=stderr,
                end='',
            )
        else:
            print(text_message)
            if text_message == "START":
                self.restart()
            elif text_message == "END" and self.won is not None:
                self.advance_gameplay_model(gradient_step=bool(self.args.train & 2))
                self.save()
            elif 'winner' in text_message and text_message['player'] == self.player:
                self.won = text_message['winner']
            elif self.player is None and 'player' in text_message:
                self.player = text_message['player']
        self.previous_time = current_time

    def advance_background_model(
        self, image_data, text_message, gradient_step=False, make_move=False
    ):
        with nullcontext() if gradient_step else torch.no_grad():
            self.background_optimizer.zero_grad()

            image = image_data_to_torch(image_data, self.args.device)
            cursor, button = mouse_data_to_torch(text_message['mouse'], device='cpu')

            latent_embedding = self.background_model.embedding(image)

            self.latent_embeddings.append(retrieve(latent_embedding))
            self.cursors.append(cursor)
            self.buttons.append(button)

            predicted_image = self.background_model.generator(latent_embedding)
            error = torch.nn.functional.l1_loss(predicted_image, image)

            if gradient_step:
                error.backward()
                self.background_optimizer.step()

            with torch.no_grad():
                predicted_cursor, predicted_button_prob, self.hidden_state = self.gameplay_model(
                    latent_embedding.detach(),
                    cursor.to(self.args.device),
                    button.to(self.args.device),
                    hidden_state=self.hidden_state,
                    limit=self.args.speed_limit,
                )
                predicted_probs = torch.softmax(predicted_button_prob.to('cpu'), dim=1)[0]
                predicted_button = torch.max(predicted_probs, dim=0)[1].numpy()
                predicted_cursor = predicted_cursor[0].to('cpu').numpy()

                if make_move:
                    MoveMouse(*predicted_cursor, click=predicted_button)

    def advance_gameplay_model(self, gradient_step=False):
        print(f'Match won: {self.won}')
        with nullcontext() if gradient_step else torch.no_grad():
            latent_embeddings = torch.cat(self.latent_embeddings, dim=0)
            cursors = torch.cat(self.cursors, dim=0)
            buttons = torch.cat(self.buttons, dim=0)

            data_iterator = DataLoader(
                TensorDataset(latent_embeddings, cursors, buttons),
                batch_size=self.args.memory,
                pin_memory=True,
                shuffle=False,
            )
            hidden_state = None
            format_string = f"iter: {{:0{len(str(len(data_iterator)))}d}}/{len(data_iterator)}"
            for iter_index, batch in enumerate(data_iterator, 1):
                latent_embedding = batch[0].to(self.args.device)
                cursor = batch[1].to(self.args.device)
                button = batch[2].to(self.args.device)

                self.gameplay_optimizer.zero_grad()
                predicted_cursor_movement, predicted_button, hidden_state = self.gameplay_model(
                    latent_embedding[:-1],
                    cursor[:-1],
                    button[:-1],
                    hidden_state=hidden_state,
                    limit=self.args.speed_limit,
                )
                error = cnc_ai.model.cursor_pos_loss(
                    cursor[1:], cursor[:-1] + predicted_cursor_movement
                ) + cnc_ai.model.button_loss(button[1:], predicted_button)
                if gradient_step:
                    if self.won:
                        error.backward()
                    else:
                        (-error).backward()
                    self.gameplay_optimizer.step()
                print(format_string.format(iter_index))

    def save(self):
        if self.args.train >= 1:
            torch.save(self.background_model, self.args.background)
        if self.args.train >= 2:
            torch.save(self.gameplay_model, self.args.gameplay)

    def restart(self):
        self.previous_time = 0
        self.latent_embeddings = []
        self.cursors = []
        self.buttons = []
        self.hidden_state = None
        self.player = None
        self.won = None


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

        learner.step(image_data, text_message)


def image_data_to_torch(image_data, device='cuda'):
    return ToTensor()(Image.open(BytesIO(image_data))).to(device)[None, :, :, :]


def mouse_data_to_torch(mouse_data, device='cuda'):
    cursor = torch.Tensor([[mouse_data['x'], mouse_data['y']]]).to(device)
    button = torch.Tensor([mouse_data['button']]).long().to(device)
    return cursor, button


def main():
    app = Application()
    app.listen(8888)
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.instance().stop()


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--background', type=str, required=True, help='background model name')
    parser.add_argument('--gameplay', type=str, required=True, help='gameplay model name')
    parser.add_argument(
        '--train',
        type=int,
        default=3,
        help='bitfield to control what to train. '
        '0: AI runs in the background but doesn\'t learn anything, '
        '1: train background model, '
        '2: train gameplay',
    )
    parser.add_argument(
        '--move',
        default=False,
        action='store_true',
        help='if set then AI can poke into the game, otherwise you are in control',
    )
    parser.add_argument('--lr', default=0.001, type=float, help='learning rate')
    parser.add_argument(
        '--memory', default=1024, type=int, help='maximum time window to backpropagate to'
    )
    parser.add_argument(
        '--device', default='cuda', type=torch.device, help='device to calculate on'
    )
    parser.add_argument(
        '--speed_limit',
        type=float,
        default=360.0,
        help='how many pixels can the cursor move between two successive calls of CNC_Advance_Instance',
    )
    parser.add_argument(
        '--apm_limit',
        type=int,
        default=60,
        help='limit how many clicks the ai can make within one minute (TODO)',
    )

    return parser.parse_args()


if __name__ == "__main__":
    learner = Learner(parse_args())
    main()
