# -*- coding: utf-8 -*-
"""
APNS Proxy Serverのクライアント

Usage:
    client = APNSProxyClient("tcp://localhost:5556", "01")
    with client:
        token = "xxae2fcdb2d325a2de86d572103bff6dd272576d43677544778c43a674407ec1"
        msg = u"これはメッセージAです"
        client.send(token, msg)

        token = "xxae2fcdb2d325a2de86d572103bff6dd272576d43677544778c43a674407ec2"
        msg = u"これはメッセージBです"
        client.send(token, msg)
"""

import zmq
import simplejson as json


RECV_TIMEOUT = 3000  # msec

COMMAND_PING = b'1'
COMMAND_TOKEN = b'2'
COMMAND_END = b'3'

DEVICE_TOKEN_LENGTH = 64
MAX_MESSAGE_LENGTH = 255


class APNSProxyClient(object):

    def __init__(self, address, application_id):
        """ZMQコンテキストとソケットの初期化"""
        if address is None:
            raise ValueError("address must be string")
        self.address = address

        self.context = zmq.Context()
        self.context.setsockopt(zmq.LINGER, 2000)

        self.client = self.context.socket(zmq.REQ)

        if not isinstance(application_id, str) or len(application_id) != 2:
            raise ValueError("application_id must be 2 length string")
        self.application_id = application_id

    def __enter__(self):
        """リモートサーバーへ接続"""
        self.client.connect(self.address)
        self.ping()

    def ping(self):
        self.client.send(COMMAND_PING)
        poller = zmq.Poller()
        poller.register(self.client, zmq.POLLIN)
        if poller.poll(RECV_TIMEOUT):
            ret = self.client.recv()
            if ret != "OK":
                raise IOError("Invalid server state %s" % ret)
        else:
            self.close()
            raise IOError("Cannot connect to APNs Proxy Server. Timeout!!")

    def send(self, token, message, sound='default', badge=None, expiry=None):
        """
        デバイストークンの送信
        """
        if len(token) != DEVICE_TOKEN_LENGTH:
            raise ValueError('Invalid token length %s' % token)
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError('Too long message')
        if isinstance(message, unicode):
            message = message.encode("utf-8")

        self.client.send(COMMAND_TOKEN + json.dumps({
            'appid': self.application_id,
            'token': token,
            'command': 'send',
            'aps': {
                'message': message,
                'sound': sound,
                'badge': badge,
                'expiry': expiry
            }
        }, ensure_ascii=True), zmq.SNDMORE)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type:
            self.close()
            return False

        # バッファに残っているメッセージを流しきる
        self.client.send(COMMAND_END)
        poller = zmq.Poller()
        poller.register(self.client, zmq.POLLIN)
        if poller.poll(RECV_TIMEOUT):
            self.client.recv()
        else:
            self.close()
            raise IOError("Server cannot respond. Some messages may lost.")
        return True

    def close(self):
        self.client.close()
        self.context.term()
