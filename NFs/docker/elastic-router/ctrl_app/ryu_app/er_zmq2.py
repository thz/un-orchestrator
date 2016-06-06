__author__ = 'Administrator'

from eventlet.green import zmq

import eventlet
from ryu.lib import hub
import logging
from doubledecker.clientSafe import ClientSafe
#Set the logger
#logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
import time
import json
from jsonrpcserver import dispatch, Methods
from jsonrpcserver.request import Request
import tornado.ioloop

CTX = zmq.Context(1)

class er_zmq:
    def __init__(self, ER_monitor, ER_instance):
        #Set the logger
        #logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
        self.log = logging.getLogger('zmq_logger')
        self.log.setLevel(logging.DEBUG)

        # monitoring class
        self.er_monitor = ER_monitor
        # Elastic Router class
        self.ER_app = ER_instance

        self.DDclient = DD_client(
            name='ryu',
            dealerurl='tcp://172.17.0.1:5555',
            keyfile='./a-keys.json',
            ER_instance=ER_instance,
            ER_monitor=ER_monitor)

        #sub_server = hub.spawn(self.DDclient.start)
        #self.DDclient = None
        #hub.connect
        sub_server = hub.spawn(self.alarm_receiver,ER_instance ,ER_monitor)
        #self.DDclient.start()

        #self.alarm_subscribe()


        #sub_server = hub.spawn(self.alarm_receiver)


    def bob_client(self):
        logging.info("STARTING BOB")
        bob = zmq.Socket(CTX, zmq.PULL)
        bob.bind("ipc:///tmp/alarm_trigger")
        # if a remote server, tcp connection would be needed
        # ./ryu_ddclient.py -k ./a-keys.json -d tcp://172.17.0.1:5555 ryu a &

        #while True:
        #    logging.debug("BOB PULLING")
        #    logging.debug("BOB GOT:", bob.recv())

        while True:
            logging.debug("BOB PULLING")
            msg = bob.recv_multipart()
            print("received :", msg)
            hub.sleep(1)


    def alarm_subscribe(self):
        self.DDclient.alarm_sub(b'sub', b'monitor_alarm', b'node')
        self.log.debug("ALARM SUBSCRIBE")
        return
        DD_proxy = zmq.Socket(CTX, zmq.REQ)
        DD_proxy.connect("ipc:///tmp/alarm_subscribe")
        DD_proxy.send_multipart([b'sub', b'monitor_alarm', b'node'])

    def alarm_receiver(self, ER_instance, ER_monitor):
        DDclient = DD_client(
            name='ryu',
            dealerurl='tcp://172.17.0.1:5555',
            keyfile='./a-keys.json',
            ER_instance=ER_instance,
            ER_monitor=ER_monitor)
        #
        # io_loop = tornado.ioloop.IOLoop.current(instance=False)

        #io_loop = tornado.ioloop.IOLoop()
        #io_loop.make_current()

        #DDclient._IOLoop = tornado.ioloop.IOLoop.current(instance=False)
        #DDclient._IOLoop.make_current()

        self.log.info("START DDclient")
        DDclient.start()

        #DDclient._IOLoop.current(instance=False).start()

        #self.DDclient._IOLoop.make_current()


    def alarm_receiver_old(self):
        self.log.debug("Waiting for ALARM")


        DD_proxy = zmq.Socket(CTX, zmq.PULL)
        DD_proxy.bind("ipc:///tmp/alarm_trigger")

        while True:
            msg = DD_proxy.recv_multipart()
            self.log.info("Received ALARM: {0}".format(msg))
            start_time = time.time()

            scaling_ports = []
            if 'scale_in' in msg[2]:
                scaling_ports = self.er_monitor.start_scale_in_default()
                self.log.info('start scale in')
                if len(scaling_ports) > 0:
                    self.ER_app.VNFs_to_be_deleted = self.ER_app.scale(scaling_ports,'in')
                    # wait unit scaling lock is released
                    self.er_monitor.scaling_lock.acquire()
                    self.er_monitor.scaling_lock.release()

            elif 'scale_out' in msg[2]:
                scaling_ports = self.er_monitor.start_scale_out_default()
                self.log.info('start scale out')
                if len(scaling_ports) > 0:
                    self.ER_app.VNFs_to_be_deleted = self.ER_app.scale(scaling_ports,'out')
                    # wait unit scaling lock is released
                    self.er_monitor.scaling_lock.acquire()
                    self.er_monitor.scaling_lock.release()

            scaling_time = time.time() - start_time
            self.log.info('scaling finished ({0} seconds)'.format(round(scaling_time, 2)))


class DD_client(ClientSafe):
    def __init__(self, name, dealerurl, keyfile, ER_instance, ER_monitor):
        super(DD_client, self).__init__(name, dealerurl, keyfile)
        self.subscriptions = []
        self.registered = False

        # monitoring class
        self.ER_monitor = ER_monitor
        # Elastic Router class
        self.ER_app = ER_instance

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

    def on_pub(self, src, topic, msg):
        self.handle_jsonrpc(src=src, msg=msg, topic=topic)

    def on_data(self, src, msg):
        self.handle_jsonrpc(src, msg, topic=None)

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
        #self.sender.send_multipart([ddsrc.encode(), "alarms".encode(), message.encode()])
        logging.info("Received ALARM: {0}".format(message))
        start_time = time.time()

        scaling_ports = []
        if 'scale_in' in message:
            scaling_ports = self.er_monitor.start_scale_in_default()
            self.log.info('start scale in')
            if len(scaling_ports) > 0:
                self.ER_app.VNFs_to_be_deleted = self.ER_app.scale(scaling_ports, 'in')
                # wait unit scaling lock is released
                self.ER_monitor.scaling_lock.acquire()
                self.ER_monitor.scaling_lock.release()

        elif 'scale_out' in message:
            scaling_ports = self.er_monitor.start_scale_out_default()
            self.log.info('start scale out')
            if len(scaling_ports) > 0:
                self.ER_app.VNFs_to_be_deleted = self.ER_app.scale(scaling_ports, 'out')
                # wait unit scaling lock is released
                self.ER_monitor.scaling_lock.acquire()
                self.ER_monitor.scaling_lock.release()

        scaling_time = time.time() - start_time
        logging.info('scaling finished ({0} seconds)'.format(round(scaling_time, 2)))


    def alarm_sub(self, action, topic, scope):

        action_ = action
        topic_ = topic.decode()
        scope_ = scope.decode()

        if b'sub' == action_:
            self.subscriptions.append((topic_, scope_))
            if self.registered:
                self.subscribe(topic_, scope_)
        elif b'unsub' == action_:
            try:
                self.subscriptions.remove((topic_, scope_))
            except ValueError as e:
                logging.error("Ryu tried to unsubscribe from a non-existing subscription")
            if self.registered:
                self.unsubscribe(topic_, scope_)
        else:
            logging.error("Ryu sent a weird command :", action_)