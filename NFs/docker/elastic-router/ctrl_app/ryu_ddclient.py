#!/usr/bin/python3
# -*- coding: utf-8 -*-
__license__ = """
  Copyright (c) 2015 Pontus Sköldström, Bertrand Pechenot

  This file is part of libdd, the DoubleDecker hierarchical
  messaging system DoubleDecker is free software; you can
  redistribute it and/or modify it under the terms of the GNU Lesser
  General Public License (LGPL) version 2.1 as published by the Free
  Software Foundation.

  As a special exception, the Authors give you permission to link this
  library with independent modules to produce an executable,
  regardless of the license terms of these independent modules, and to
  copy and distribute the resulting executable under terms of your
  choice, provided that you also meet, for each linked independent
  module, the terms and conditions of the license of that module. An
  independent module is a module which is not derived from or based on
  this library.  If you modify this library, you must extend this
  exception to your version of the library.  DoubleDecker is
  distributed in the hope that it will be useful, but WITHOUT ANY
  WARRANTY; without even the implied warranty of MERCHANTABILITY or
  FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
  License for more details.  You should have received a copy of the
  GNU Lesser General Public License along with this program.  If not,
  see <http://www.gnu.org/licenses/>.
"""

import argparse, logging, zmq, json
from doubledecker.clientSafe import ClientSafe
from jsonrpcserver import dispatch, Methods
from jsonrpcserver.request import Request

Request.notification_errors = True


# Inherit ClientSafe and implement the abstract classes
# ClientSafe does encryption and authentication using ECC (libsodium/nacl)


class SecureCli(ClientSafe):
    def __init__(self, name, dealerurl, customer, keyfile):
        super().__init__(name, dealerurl, keyfile)
        #super().__init__(name, dealerurl, customer, keyfile)

        self.subscriptions = []
        self.registered = False
        context = zmq.Context.instance()
        self.sender = context.socket(zmq.PUSH)
        self.receiver = context.socket(zmq.REP)

        self.receiver.bind('ipc:///tmp/alarm_subscribe')
        self.alarm_sub_stream = zmq.eventloop.zmqstream.ZMQStream(self.receiver,
                                                                  self._IOLoop)
        self.alarm_sub_stream.on_recv(self.alarm_sub)

        self.sender.connect('ipc:///tmp/alarm_trigger')

        self.methods = Methods()
        self.methods.add_method(self.alarms)

    # callback called upon registration of the client with its broker
    def on_reg(self):
        logging.info("The client is now connected")
        self.registered = True
        for topic_, scope_ in self.subscriptions:
            self.subscribe(topic_, scope_)

    # callback called when the client detects that the heartbeating with
    # its broker has failed, it can happen if the broker is terminated/crash
    # or if the link is broken
    def on_discon(self):
        logging.warning("The client got disconnected")
        self.registered = False


    # callback called when the client receives an error message
    def on_error(self, code, msg):
        logging.error("ERROR n#%d : %s" % (code, msg))


    def handle_jsonrpc(self, src, msg, topic=None):
        request = json.loads(msg.decode('UTF-8'))

        if 'error' in request:
            logging.error(str(request['error']))
            return

        if 'result' in request:
            logging.info(str(request['result']))
            return

        # include the 'ddsrc' parameter so the
        # dispatched method knows where the message came from
        if 'params' not in request:
            request['params'] = {}

        request['params']['ddsrc'] = src.decode()
        response = dispatch(self.methods, request)

        # if the http_status is 200, its request/response, otherwise notification
        if response.http_status == 200:
            logging.info("Replying to %s with %s" % (str(src), str(response)))
            self.sendmsg(src, str(response))
        # notification, correctly formatted
        elif response.http_status == 204:
            pass
        # if 400, some kind of error
        # return a message to the sender, even if it was a notification
        elif response.http_status == 400:
            self.sendmsg(src, str(response))
            logging.error("Recived bad JSON-RPC from %s, error %s" % (str(src), str(response)))
        else:
            logging.error(
                "Recived bad JSON-RPC from %s \nRequest: %s\nResponose: %s" % (str(src), msg.decode(), str(response)))

    def alarms(self, ddsrc, message):
        #self.sender.send_multipart([ddsrc, "alarms", message])
        self.sender.send_multipart([ddsrc.encode(), "alarms".encode(), message.encode()])
        
    def on_pub(self, src, topic:str, msg:str):
        self.handle_jsonrpc(src=src, msg=msg, topic=topic)

    def on_data(self, src:str, msg:str):
        self.handle_jsonrpc(src, msg, topic=None)

    def alarm_sub(self, msg):
        if len(msg) < 3:
            logging.error("Malformed alarm subscription")
            return
        action_ = msg.pop(0)
        topic_ = msg.pop(0).decode()
        scope_ = msg.pop(0).decode()

        if b'sub' == action_:
            self.subscriptions.append((topic_,scope_))
            if self.registered:
                self.subscribe(topic_, scope_)
        elif b'unsub' == action_:
            try:
                self.subscriptions.remove((topic_,scope_))
            except ValueError as e:
                logging.error("Ryu tried to unsubscribe from a non-existing subscription")
            if self.registered:
                self.unsubscribe(topic_,scope_)
        else:
            logging.error("Ryu sent a weird command :", action_)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generic message client")
    parser.add_argument('name', help="Identity of this client")
    parser.add_argument('customer', help="Name of the customer to get the keys (i.e. 'a' for the customer-a.json file)")
    parser.add_argument(
        '-d',
        "--dealer",
        help='URL to connect DEALER socket to, "tcp://1.2.3.4:5555"',
        nargs='?',
        default='tcp://127.0.0.1:5555')
    parser.add_argument(
        '-f',
        "--logfile",
        help='File to write logs to',
        nargs='?',
        default=None)
    parser.add_argument(
        '-l',
        "--loglevel",
        help='Set loglevel (DEBUG, INFO, WARNING, ERROR, CRITICAL)',
        nargs='?',
        default="INFO")
    parser.add_argument(
        '-k',
        "--keyfile",
        help='File containing the encryption/authentication keys)',
        nargs='?',
        default='')

    args = parser.parse_args()

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.loglevel)

    logging.basicConfig(format='%(levelname)s:%(message)s', filename=args.logfile, level=numeric_level)

    logging.info("Safe client")
    genclient = SecureCli(name=args.name,
                          dealerurl=args.dealer,
                          customer=args.customer,
                          keyfile=args.keyfile)

    logging.info("Starting DoubleDecker example client")
    logging.info("See ddclient.py for how to send/recive and publish/subscribe")
    genclient.start()
