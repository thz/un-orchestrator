__author__ = 'Administrator'

from eventlet.green import zmq
import eventlet
from ryu.lib import hub
import logging
#Set the logger
#logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
import time

CTX = zmq.Context(1)

class er_zmq:
    def __init__(self, monitor_instance, ER_instance):
        #Set the logger
        #logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
        self.log = logging.getLogger('zmq_logger')
        self.log.setLevel(logging.DEBUG)

        # monitoring class
        self.er_monitor = monitor_instance
        # Elastic Router class
        self.ER_app = ER_instance

        self.alarm_subscribe()

        sub_server = hub.spawn(self.alarm_receiver)


    def bob_client(self):
        logging.info("STARTING BOB")
        bob = zmq.Socket(CTX, zmq.PULL)
        bob.bind("ipc:///tmp/alarm_trigger")
        # if a remote server, tcp connection would be needed

        #while True:
        #    logging.debug("BOB PULLING")
        #    logging.debug("BOB GOT:", bob.recv())

        while True:
            logging.debug("BOB PULLING")
            msg = bob.recv_multipart()
            print("received :", msg)
            hub.sleep(1)


    def alarm_subscribe(self):
        self.log.debug("ALARM SUBSCRIBE")
        DD_proxy = zmq.Socket(CTX, zmq.REQ)
        DD_proxy.connect("ipc:///tmp/alarm_subscribe")
        #DD_proxy.send_multipart([b'sub', b'alarms', b'all'])
        DD_proxy.send_multipart([b'sub', b'monitor_alarm', b'node'])

    def alarm_receiver(self):
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
            logging.info('scaling finished ({0} seconds)'.format(round(scaling_time, 2)))