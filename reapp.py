#!/usr/bin/python3
import tornado
import tornado.web
import tornado.httpserver
import tornado.ioloop
import json
from tornado import websocket
from collections import OrderedDict
from sms_struct import TableSms

import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('localhost', 5001))

class websocketHandler(websocket.WebSocketHandler):

    def open(self):
        self.initial_number = 0
        self.count = 0
        self.table = TableSms()
        if self.application.mainloop:
            self.application.mainloop.on_init()
            self.application.mainloop.send = self.send
        else:
            print('conection received')

    def send(self, data):
        self.write_message(data)

    def on_message(self, msg):
        # client.send(bytes(str(msg).encode()))
        data = json.loads(msg)

        if data["op"] == "initial_count":
            self.initial_number = int(data["data"])

        elif data["op"] == "init_data":
            self.count = len(self.table.display_name_list)
            self.table.add_entry(data["data"])
            if self.application.mainloop:
                self.application.mainloop.init_data("received " + str(self.count) + " out of " + str(self.initial_number) + " conversation")
            else:
                print("received " + str(self.count) + " out of " + str(self.initial_number) + " conversation")

        elif data["op"] == "done":

            if self.application.mainloop:
                # self.application.mainloop.done(self.sms_dict)
                self.application.mainloop.done()
            else:
                # print(self.sms_dict)
                # print("done")
                print("done")

        elif data["op"] == "sms_recv":
            if self.application.mainloop:
                thread_id = self.table.get_thread_id_by_number(data["data"]["number"])
                data["data"]["thread_id"] = thread_id
                self.application.mainloop.on_recv(data["data"])
                client.send(bytes(str(data["data"]).encode()))
                client.send(b'\n')
            else:
                print("sms received")
                print(data["data"])

        elif data["op"] == "sms_confirmation":
            if self.application.mainloop:
                client.send(bytes(str(data["data"]).encode()))
                client.send(b'\n')
                self.application.mainloop.on_send_confirmation(data)
            else:
                print("sms confirmation")
                print(data["data"])


    def on_close(self):
        if not self.application.mainloop:
            print("connection close")


class App(tornado.web.Application):

    def __init__(self, mainloop=None):
        self.mainloop = mainloop
        if not mainloop:
            print("server started")
        super(App, self).__init__([(r"/", websocketHandler)], debug=True)


def start_server(mainloop):
    app = App(mainloop)
    server = tornado.httpserver.HTTPServer(app)
    server.listen(8000)
    tornado.ioloop.IOLoop.instance().start()

def main():
    app = App()
    httpserver = tornado.httpserver.HTTPServer(app)
    httpserver.listen(8000)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
