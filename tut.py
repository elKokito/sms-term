#!/usr/bin/python3
import urwid
import os
import threading
import sys
import asyncio
import json
import socket
import app

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect(('localhost', 5000))

class ContactName(urwid.ListBox):

    def __init__(self, data):

        numbers = data.keys()
        body = []
        self.longest_name = 0
        self.button_list = []
        for number in numbers:
            if data[number][0]["name"] != "unknown":
                button = urwid.Button(("name", data[number][0]["name"]))
                self.button_list.append({"button": button, "number": number})
                body.append(urwid.AttrMap(button, "name"))
                if len(data[number][0]) > self.longest_name:
                    self.longest_name = len(data[number][0])
            else:
                button = urwid.Button(number)
                self.button_list.append({"button": button, "number": number})
                body.append(button)
                if len(number) > self.longest_name:
                    self.longest_name = len(number)
        super(ContactName, self).__init__(urwid.SimpleFocusListWalker(body))

    def get_index_for_widget(self, name):
        return self.body.index(self.focus)

    def get_index_for_name(self, name):
        for item in self.body:
            if item.base_widget.label == name:
                return self.body.index(item)


class NameMsg(urwid.Columns):

    def __init__(self, data):
        urwid.register_signal(NameMsg, "edit_sms")
        self.data = data
        self.list_name_widget = self.make_list_name_widget(data)
        self.list_sms_widget = self.make_list_sms_widget(data)
        length_max_name = self.list_name_widget.longest_name
        for btn in self.list_name_widget.button_list:
            urwid.connect_signal(btn["button"], 'click', self.clicked, btn["number"])
        super(NameMsg, self).__init__([(length_max_name + 4, self.list_name_widget), self.list_sms_widget[0]])

    def make_list_name_widget(self, data):
        return ContactName(data)


    def make_list_sms_widget(self, data):
        widget_list = []
        for name, info in data.items():
            body = []
            for sms in info:
                client_socket.send(bytes(str(sms).encode()))
                client_socket.send(b'\n')
                if sms["type"] == "1":
                    body.append(urwid.Text(("sms_recv",sms["sms"]), "right"))
                else:
                    body.append(urwid.Text(("sms_send",sms["sms"]), "right"))
            widget_list.append(urwid.ListBox(urwid.SimpleFocusListWalker(body)))
        return widget_list


    def render(self, size, focus=False):
        focused_widget = self.get_focus_widgets()
        index = self.list_name_widget.get_index_for_widget(focused_widget[0])
        self.widget_list[1] = self.list_sms_widget[index]
        return urwid.Columns.render(self, size, focus)

    def clicked(self, widget, number):
        self.number_to_send = number
        self.widget_to_update = self.widget_list[1]
        urwid.emit_signal(self, "edit_sms")
        client_socket.send(b'button clicked\n')

    def new_sms(self, data):
        client_socket.send(b'new sms\n')
        name = data["name"] if data["name"] != "unknown" else data["number"]
        index = self.list_name_widget.get_index_for_name(name)
        self.list_sms_widget[index].body.insert(0, urwid.Text(("sms_recv", data["sms"]), "right"))
        self.list_sms_widget[index].set_focus_path([0])
        self.widget_list[1] = self.list_sms_widget[index]
        # need to shift list of name to get the new one on the top
        widget = self.list_name_widget.body[index]
        for i in range(index, 0, -1):
            self.list_name_widget.body[i] = self.list_name_widget.body[i-1]
        self.widget_list[1] = self.list_name_widget

    def send_confirmation(self, data):
        # client_socket.send(bytes(str(self.widget_to_update).encode()))
        # client_socket.send(b'\n')
        # client_socket.send(bytes(str(self.widget_to_update.body[0]).encode()))
        # client_socket.send(b'\n')
        client_socket.send(b'send_confirmation method\n')
        widget_text = self.widget_to_update.body[0]
        widget_text = urwid.Text(("sms_send", widget_text.text), "right")
        self.widget_to_update.body[0] = widget_text


class Top(urwid.ListBox):

    def __init__(self, data, mainloop):
        self.mainloop = mainloop
        self.send_sms = mainloop.on_send
        self.name_msg = NameMsg(data)
        urwid.connect_signal(self.name_msg, 'edit_sms', self.focus_edit_sms)
        self.input_text = urwid.Edit(multiline=True)
        top = urwid.BoxAdapter(self.name_msg, os.get_terminal_size()[1] - 5)
        super(Top, self).__init__(urwid.SimpleFocusListWalker([top, self.input_text]))

    def keypress(self, size, key):
        if self.focus == self.input_text:
            client_socket.send(b'keypress inside input_text widget\n')
            if key == "enter":
                text = self.body[1].get_edit_text()
                msg_to_send = json.dumps({"number": self.name_msg.number_to_send, "msg": text})
                self.send_sms(msg_to_send)
                client_socket.send(bytes(str(self.name_msg.widget_to_update.body).encode()))
                client_socket.send(b'\n')
                self.name_msg.widget_to_update.body.insert(0, urwid.Text(("sms_send_query", text), "right"))
                self.body[1].set_edit_text("")
            elif key == "esc":
                if self.body[1].get_edit_text() == "":
                    raise urwid.ExitMainLoop
                self.body[1].set_edit_text("")
                self.set_focus(0)
            else:
                return super(Top, self).keypress(size, key)
        else:
            return super(Top, self).keypress(size, key)

    def on_receive(self, data):
        self.name_msg.new_sms(data)

    def send_confirmation(self, data):
        self.name_msg.send_confirmation(data)


    def focus_edit_sms(self):
        self.set_focus_path([1])
        client_socket.send(b'cursor should be in edit\n')
        self.keypress((1,1), "left")


class mainLoop(urwid.MainLoop):

    def __init__(self):
        palette = [("name", "", "", "", "#6dd", "black"),
                   ("sms_recv", "", "", "", "#6dd", "black"),
                   ("sms_send", "", "", "", "g52", "black"),
                   ("bg", "", "", "", "", "black"),
                   ("sms_send_query", "", "", "", "#ff0", "black")]
        top = urwid.Filler(urwid.Text("waiting phone connection"))
        t = threading.Thread(target=app.start_server, args=(self,), daemon=True)
        t.start()
        self.top = None
        super(mainLoop, self).__init__(top, palette, unhandled_input=self.quit)

    def quit(self, key):
        if key == 'q':
            raise urwid.ExitMainLoop

    def on_init(self):
         top = urwid.Filler(urwid.Text("connection opened"))
         self.widget = top
         self.draw_screen()


    def init_data(self, info):
        top = urwid.Filler(urwid.Text(info))
        self.widget = top
        self.draw_screen()

    def done(self, data):
        top = Top(data, self)
        self.top = top
        self.widget = urwid.AttrMap(top, "bg")
        self.draw_screen()

    def on_recv(self, data):
        self.top.on_receive(data)
        self.draw_screen()

    def on_send(self, data):
        pass

    def on_send_confirmation(self, data):
        client_socket.send(bytes(str(data).encode()))
        client_socket.send(b'\n')
        self.top.send_confirmation(data)
        self.draw_screen()


def main():
    mainloop = mainLoop()
    mainloop.screen.set_terminal_properties(colors=256)
    mainloop.run()
    sys.exit(0)

if __name__ == "__main__":
    main()
