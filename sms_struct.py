import json
import socket
from collections import OrderedDict
import socket

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('localhost', 5002))

class Contact:

    def __init__(self, data):
        self.name = data["name"]
        self.thread_id = data["thread_id"]
        self.display_name = data["name"] if data["name"] != "unknown" else data["number"]
        self.number = data["number"]
        self.widget = None


class Sms:

    def __init__(self, data):
        self.sms = data["sms"]
        self.thread_id = data["thread_id"]
        self.read = data["read"]
        self.type = data["type"]
        self.time = data["time"]
        self.widget = None


class TableSms:
    class __TableSms:
        def __init__(self):
            self.sms_table = OrderedDict()
            self.display_name_list = []

        def add_entry(self, data):
            sms = Sms(data)
            contact = Contact(data)
            if data["thread_id"] not in self.sms_table.keys():
                self.sms_table[data["thread_id"]] = [(contact, sms)]
                self.display_name_list.append((contact.display_name, contact))
            else:
                self.sms_table[data["thread_id"]].append((contact, sms))

        def longest_name(self):
            lenght = 0
            for display_name, contact in self.display_name_list:
                if len(display_name) > lenght:
                    lenght = len(display_name)
            return lenght

        def get_index(self, widget):
            for display_name, contact in self.display_name_list:
                client.send(bytes(str(contact.widget).encode()))
                client.send(b'\n')
                client.send(bytes(str(widget).encode()))
                client.send(b'\n')
                if widget == contact.widget:
                    return contact.thread_id

        def get_thread_id_by_number(self, number):
            for display_name, contact in self.display_name_list:
                if contact.number == number:
                    return contact.thread_id

    instance = None

    def __init__(self):
        if not TableSms.instance:
            TableSms.instance = TableSms.__TableSms()

    def __getattr__(self, name):
        return getattr(self.instance, name)


