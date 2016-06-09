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
# Some parts, Copyright © 2016 SICS Swedish ICT AB

import argparse
import logging
import socket
import socketserver
import threading
import zmq
import time
import json
#import os
import sys
from doubledecker.clientSafe import ClientSafe
from math import sqrt
from subprocess import Popen
import pdb

# Inherit ClientSafe and implement the abstract classes
# ClientSafe does encryption and authentication using ECC (libsodium/nacl)


class MonitoringDataHandler(socketserver.BaseRequestHandler):

    def setup(self):
        context = zmq.Context.instance()
        self.socket = context.socket(zmq.REQ)
        self.socket.connect('inproc://handlers')

    def handle(self):
        data = self.request.recv(1024).strip()
        self.socket.send(data)


class SecureCli(ClientSafe):
#    def __init__(self, name, dealerurl, customer, keyfile, mpath, mport=55555, qport=54736, hello=True, ramon_args=None):
    def __init__(self, name, dealerurl, keyfile, mpath, mport=55555, qport=54736, hello=True, ramon_args=None):
#        super().__init__(name, dealerurl, customer, keyfile)
        super().__init__(name, dealerurl, keyfile)

        self.b = True

        context = zmq.Context.instance()
        self.handlers = context.socket(zmq.REP)
        self.handlers.bind('inproc://handlers')

        self.handlersThread = threading.Thread(
            target=self.results_sender)

        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.tcp_server = socketserver.ThreadingTCPServer(('127.0.0.1', mport),
                                             MonitoringDataHandler)
        self.tcp_server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_server.daemon = True
        self.serverThread = threading.Thread(
            target=self.tcp_server.serve_forever)

        self.tcp_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.mname = name
        self.mpath = mpath
        self.mport = mport
        self.qport = qport
        self.hello = hello
        self.ramon_args = ramon_args
        self.last_ramon_data = None

    # callback called automatically everytime a point to point is sent at
    # destination to the current client
    # Expects a Json-Rpc 2.0 like this
    # {"jsonrpc": "2.0", "method": <method name>, "params": { ... }}
    def on_data(self, src, msg):
#        print("DATA from %s: %s" % (str(src), str(msg)))
        logging.debug("DATA from %s: %s" % (str(src), str(msg)))
        msg_json = json.loads(msg.decode("utf-8"))
        try:
            meth = msg_json['method']
            logging.debug('Command received: ' + meth)
            if 'status' == meth:
                logging.warning('NYI command received: ' + meth)
            if meth in ['interface', 'sample_rate', 'estimation_interval', 'meter_interval', 'link_speed', 'alarm_trigger', 'cutoff']:
                self.send_config(self.get_config_param(msg_json,meth))
            elif 'exit' == meth:
                self.send_config({'exit': True})
            elif 'pause' == meth:
                self.send_config({'pause': True})
            elif 'resume' == meth:
                self.send_config({'resume': True})
            elif 'poll_data' == meth:
                # We get this notification from the aggregator
                if self.last_ramon_data != None:
                    filtered_data = self.filter_ramon_data(self.last_ramon_data)
                    rpc_obj = {"jsonrpc": "2.0", "method": "rate_data", "params": filtered_data}
                    rpc_obj_json = json.dumps(rpc_obj)
                    self.publish('measurement', rpc_obj_json)
            elif 'start' == meth:
                # We get this notification from the MMP
                self.start_ramon()
            else: logging.warning('Unknown command received:' + meth)
        except KeyError as ke:
            logging.warning('Malformed Json-Rpc: ' + str(msg_json))

    def get_config_param(self,msg_json, meth):
        return {meth: msg_json['params'].get(meth)}

    def send_config(self,config):
        self.tcp_client.connect(('127.0.0.1', self.qport))
        self.tcp_client.sendmsg(config)
        self.tcp_client.close()


    def start_ramon(self):
        # Register this rate monitor with the aggregator
        rpc_obj = {"jsonrpc": "2.0", "method": "add_monitor", "params": {"name": self.mname}}
        rpc_obj_json = json.dumps(rpc_obj)
        self.publish('measurement', rpc_obj_json)
        # and start a RAMON instance
        # Popen(["xterm", "-geometry", "80x45+0+0", "-wf", "-T", "%s_ramon"%self.mname,
        #        "-e", self.mpath + " -b %s %s ; read"%(str(self.mport), ' '.join(self.ramon_args))])
        Popen([self.mpath, "-b", str(self.mport)]+self.ramon_args)


    # callback called upon registration of the client with its broker
    def on_reg(self):
#        print("The client is now connected")
        logging.info("The client is now connected")
        # Say hello to the MMP
        if self.hello:
            rpc_obj = {"jsonrpc": "2.0", "method": "hello", "params": {"name": self.mname, "type": "ratemon"}}
            rpc_obj_json = json.dumps(rpc_obj)
            self.publish('unify:mmp', rpc_obj_json)
        else:
            self.start_ramon()

    # callback called when the client detects that the heartbeating with
    # its broker has failed, it can happen if the broker is terminated/crash
    # or if the link is broken
    def on_discon(self):
#        print("The client got disconnected")
        logging.info("The client got disconnected")

    # callback called when the client receives an error message
    def on_error(self, code, msg):
#        print("ERROR n#%d : %s" % (code, msg))
        logging.error("ERROR n#%d : %s" % (code, msg))

    # callback called when the client receives a message on a topic he
    # subscribed to previously
    def on_pub(self, src, topic, msg):
#        print("PUB %s from %s: %s" % (str(topic), str(src), str(msg)))
        logging.info("PUB %s from %s: %s" % (str(topic), str(src), str(msg)))

    def start(self):
        logging.info('Starting to serve requests')
        self.serverThread.daemon = True # [PD] 2016-06-07, see if this helps on shutdown ...
        self.serverThread.start()
        self.handlersThread.daemon = True # [PD] 2016-06-07, see if this helps on shutdown ...
        self.handlersThread.start()
        super().start()

    def shutdown(self):
        # Un-register this monitor with the aggregator
        logging.info("\nShutting down")
        rpc_obj = {"jsonrpc": "2.0", "method": "remove_monitor", "params": {"name": self.mname}}
        rpc_obj_json = json.dumps(rpc_obj)
        self.publish('measurement', rpc_obj_json)
        #
        logging.debug("shutdown(): before 'self.serverThread.join()'")
        self.serverThread.join()
        logging.debug("shutdown(): before 'self.handlersThread.join()'")
        self.handlersThread.join()
        logging.debug("shutdown(): before 'self.tcp_server.shutdown()'")
        self.tcp_server.shutdown()
        logging.debug("shutdown(): before 'self.tcp_server.server_close()'")
        self.tcp_server.server_close()
        logging.debug("shutdown(): before 'super.shutdown()'")
        super().shutdown()

    def results_sender(self):
        while True:
#            pdb.set_trace()
            rate_data = self.handlers.recv().decode('utf-8')
            results = json.loads(rate_data)
            print(".",end="",flush=True)
            logging.debug(results)
            if 'exited' in results:
                self.shutdown()
            elif 'initialized' in results:
                pass
            else:
                send_immediate = True
                send_immediate = False
                if send_immediate:
                    filtered_data = self.filter_ramon_data(results)
                    rpc_obj = {"jsonrpc": "2.0", "method": "rate_data", "params": filtered_data}
                    rpc_obj_json = json.dumps(rpc_obj)
                    self.publish('measurement', rpc_obj_json)
                else:
                    self.last_ramon_data = results
            self.handlers.send(b'')


    def filter_ramon_data(self,ramon_data):
#        pdb.set_trace()
        result = {}
        result['lm'] = float(ramon_data['mu_rx'])
        result['lsd'] = sqrt(float(ramon_data['sigma2_rx']))
        result['name'] = self.mname
        result['linerate'] = int(ramon_data['linerate'])
        result['overload_risk'] = ramon_data['overload_risk_rx']
        return result

    # NOTE: Keep this code as a reference on how to send a configuration message to the rate monitor.
    def results_sender_OLD(self):
        while True:
            results = self.handlers.recv()
            print(results)
            if self.b:
                    print("changing leek speed")
                    time.sleep(1)
                    self.tcp_client.connect(('127.0.0.1', 54736))
                    message_ = {'link_speed': 42}
                    print(message_)
                    self.tcp_client.send(bytes(json.dumps(message_), encoding='utf-8'))
                    reply = self.tcp_client.recv(1024)
                    print(reply)
                    self.b = False
            # self.sendmsg('agg', results)
            self.handlers.send(b'')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Generic message client")
    parser.add_argument('name', help="Identity of this client")
#    parser.add_argument( 'customer', help="Name of the customer to get the keys (i.e. 'a' for the customer-a.json file)")
    parser.add_argument(
        '-d',
        "--dealer",
        help='URL to connect DEALER socket to (Default: %(default)s)',
        nargs='?',
        default='tcp://127.0.0.1:5555')
    parser.add_argument(
        '-f',
        "--logfile",
        help='File to write logs to (Default: %(default)s)',
        nargs='?',
        default=None)
    parser.add_argument(
        '-l',
        "--loglevel",
        help='Set loglevel (DEBUG, INFO, WARNING, ERROR, CRITICAL) (Default: %(default)s)',
        nargs='?',
        default="INFO")
    parser.add_argument(
        '-k',
        "--keyfile",
        help='File containing the encryption/authentication keys',
        nargs='?',
        default='')
    parser.add_argument(
        '-n',
        "--no_hello",
        help='Do not send an hello to the MMP at startup (used when debugging). (Default: %(default)s)',
        action='store_true')
    parser.add_argument(
        '-p',
        "--ramon_port",
        help='Port for receiving rate monitor data (Default: %(default)s)',
        nargs='?',
        type=int,
        default='55555')
    parser.add_argument(
        '-q',
        "--config_port",
        help='Port for sending configuration to the rate monitor (Default: %(default)s)',
        nargs='?',
        type=int,
        default='54736')
    parser.add_argument(
        '-r',
        "--ramon_path",
        help='Path to the RAMON startup program (Default: %(default)s)',
        nargs='?',
        default='ramon/run_monitor.py')
    parser.add_argument(
        '-a',
        "--ramon_args",
        help='List of arguments to RAMON (Default: %(default)s)',
        nargs=argparse.REMAINDER)

    args = parser.parse_args()

    numeric_level = getattr(logging, args.loglevel.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.loglevel)

    logging.basicConfig(format='%(levelname)s:%(message)s', filename=args.logfile, level=numeric_level)

    logging.info("Safe client")
    genclient = SecureCli(name=args.name,
                          dealerurl=args.dealer,
#                          customer=args.customer,
                          keyfile=args.keyfile,
                          mpath=args.ramon_path,
                          mport=args.ramon_port,
                          qport=args.config_port,
                          hello= not args.no_hello,
                          ramon_args=args.ramon_args)

    logging.info("Starting DoubleDecker example client")
    logging.info("See ddclient.py for how to send/recive and publish/subscribe")
    genclient.start()
