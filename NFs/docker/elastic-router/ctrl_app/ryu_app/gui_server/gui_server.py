
# inspired from https://gist.github.com/abhinavsingh/6378134

from eventlet.green import zmq
from zmq.eventloop import ioloop
from zmq.eventloop.zmqstream import ZMQStream
ioloop.install()

import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.ioloop import IOLoop
ioloop = IOLoop.instance()

import os
import logging

from threading import Thread
import multiprocessing
from ryu.lib import hub
import gipc
import time

from tornado.options import define, options, parse_command_line



class IndexHandler(tornado.web.RequestHandler):
    def initialize(self, host_ip='localhost', host_port='8888'):
        self.host_ip = host_ip
        self.host_port = host_port

    def get(self):
        self.render("index_template.html", host_ip=self.host_ip, host_port=self.host_port)



class WebSocketHandler(tornado.websocket.WebSocketHandler):

    #def initialize(self):

        # with open("some_image.png", "rb") as imageFile:
        #    self.str = base64.b64encode(imageFile.read())


    def open(self):
        CTX = zmq.Context(1)
        self.socket = zmq.Socket(CTX, zmq.PULL)
        self.socket.bind("ipc:///tmp/ws_message")
        self.stream = ZMQStream(self.socket)
        self.stream.on_recv(self.send_data)

        self.write_message('parsed_nffg.json')
        logging.info('new connection')

    def on_message(self, message):
        #self.write_message('echo:{0}'.format(message))
        logging.info('recv:{0}'.format(message))

    def on_close(self):
        self.stream.close()
        self.socket.close()
        logging.info('connection closed')

    def send_data(self, data):
        self.write_message(data[0])


class web_server():
    def __init__(self, host_port):

        #define("port", default=8888, help="run on the given port", type=int)

        self.settings = {
            "static_path": os.path.dirname(__file__),
            "plugin_path": os.path.join(os.path.dirname(__file__), "plugins")
        }

        #sender = zmq.Socket(CTX, zmq.PUSH)
        #sender.connect('ipc:///tmp/ws_message')

        #gui_pipe_recv, self.gui_pipe_send = gipc.pipe()
        #self.queue = multiprocessing.Queue()
        # need to use gipc process, other thread types block the main
        p = gipc.start_process(target=self.start_server, args=(), kwargs=dict(host_port=host_port))
        #p = multiprocessing.Process(target=self.start_server, args=(self.queue,), kwargs=dict(host_port=host_port))
        #p.start()

    def start_server(self, host_ip='localhost', host_port=10001):
        # locally listens to 8888 (inside docker container)
        # but this is mapped by the orchestrator to host_port
        app = tornado.web.Application([
            (r'/', IndexHandler, dict(host_ip=host_ip, host_port=host_port)),
            (r'/ws', WebSocketHandler),
            (r"/(sigma\.min\.js)", tornado.web.StaticFileHandler,
             dict(path=self.settings['static_path'])),
            (r"/(sigma\.parsers.*)", tornado.web.StaticFileHandler,
             dict(path=self. settings['plugin_path'])),
            (r"/(sigma\.layout.*)", tornado.web.StaticFileHandler,
             dict(path=self.settings['plugin_path'])),
            (r"/(.*\.json)", tornado.web.StaticFileHandler,
             dict(path=self.settings['static_path'])),
        ])

        app.listen(8888)
        logging.info('start GUI')
        tornado.ioloop.IOLoop.instance().start()



if __name__ == '__main__':
    parse_command_line()
    app.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()