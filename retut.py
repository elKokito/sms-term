#!/usr/bin/python3
import urwid
import os
import threading
import sys
import json
import socket
import reapp
from sms_struct import *
import notify2

# client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# client_socket.connect(('localhost', 5000))
global_data = TableSms()

class MyButton(urwid.Button):

    def __init__(self, label, thread_id):
        self.thread_id = thread_id
        super(MyButton, self).__init__(label)

class ContactsWidget(urwid.ListBox):

    def __init__(self):

        body = []
        for display, contact in global_data.display_name_list:
            button = MyButton(display, contact.thread_id)
            contact.widget = button
            body.append(urwid.AttrMap(button, "name"))
        super(ContactsWidget, self).__init__(urwid.SimpleFocusListWalker(body))

    def get_focus(self):
        return self.focus

    def get_index_by_name(self, display_name):
        for item in self.body:
            if item.base_widget.label == display_name:
                return self.body.index(item)


class SmsWidget(list):

    def __init__(self, *args):
        global global_data
        list.__init__(self, *args)
        self.mapping = {}
        for thread_id in global_data.sms_table:
            sms_list = global_data.sms_table[thread_id]
            widget_list = self.make_widget(sms_list)
            self.append(widget_list)
            self.mapping.update({thread_id: widget_list})

    def make_widget(self, sms_list):
        body = []
        for contact, sms in sms_list:
            attr = "sms_recv" if sms.type == str(1) else "sms_send"
            text_widget = urwid.Text((attr, sms.sms), "right")
            sms.widget = text_widget
            body.append(text_widget)
        return urwid.ListBox(urwid.SimpleFocusListWalker(body))


class GridContactMsgWidget(urwid.Columns):

    def __init__(self):
        self.contacts = ContactsWidget()
        self.sms = SmsWidget()
        global global_data
        length = global_data.longest_name()
        contact_size = length + 4
        sms_size = os.get_terminal_size()[0] - length - 5
        sms_size = max(sms_size, 50)
        super(GridContactMsgWidget, self).__init__([(contact_size, self.contacts), (sms_size, self.sms[0])])

    def render(self, size, focus=False):
        focused_widget =  self.contacts.get_focus().base_widget
        thread_id = global_data.get_index(focused_widget)
        self.widget_list[1] = self.sms.mapping[thread_id]
        return urwid.Columns.render(self, size, focus)

    def move_to_top(self, contact, text, attr):
        new_sms = urwid.Text((attr, text), "right")
        index = self.contacts.get_index_by_name(contact.display_name)
        widget = self.contacts.body[index]
        for i in range(index, 0, -1):
            self.contacts.body[i] = self.contacts.body[i-1]
        self.contacts.body[0] = widget
        self.contacts.set_focus(0)

        #add text widget in self.sms
        self.sms.mapping[contact.thread_id].body.insert(0, new_sms)
        self.widget_list[1] = self.sms.mapping[contact.thread_id]
        self.widget_list[1].set_focus(0)

    def send_confirmation(self, data):
        text = self.widget_list[1].body[0]
        self.widget_list[1].body[0] = urwid.Text(("sms_send", text.text), "right")

class EditSms(urwid.Edit):

    def __init__(self):
        urwid.register_signal(EditSms, "send_signal")
        super(EditSms, self).__init__(multiline=True)

    def keypress(self, size, key):
        if key == "enter":
            text = self.get_edit_text()
            urwid.emit_signal(self, "send_signal", text)
            self.set_edit_text("")
        else:
            return super(EditSms, self).keypress(size, key)


class Top(urwid.ListBox):

    def __init__(self, mainloop):
        self.mainloop = mainloop
        self.grid = GridContactMsgWidget()
        self.edit = EditSms()
        urwid.connect_signal(self.edit, "send_signal", self.send_sms)
        contact_msg = urwid.BoxAdapter(self.grid, os.get_terminal_size()[1] - 2)
        global global_data
        for display_name, contact_obj in global_data.display_name_list:
            urwid.connect_signal(contact_obj.widget, "click", self.click, contact_obj.thread_id)
        super(Top, self).__init__(urwid.SimpleFocusListWalker([contact_msg, self.edit]))

        # self.receiver = [(contact, sms),... ]
        self.receiver = None

    def click(self, widget, thread_id):
        self.receiver = global_data.sms_table[thread_id]
        self.set_focus(1)
        self.keypress((1,1), "left")

    def send_sms(self, text):
        contact = self.receiver[0][0]
        number = contact.number
        self.mainloop.send(json.dumps({"number": number, "msg": text}))
        # move name to top and add text to sms
        self.grid.move_to_top(contact, text, "sms_send_query")

    def send_confirmation(self, data):
        self.grid.send_confirmation(data)

    def on_receive(self, data):
        # client_socket.send(b'on_receive in top\n')
        # client_socket.send(bytes(str(data).encode()))
        contact = global_data.sms_table[data["thread_id"]][0][0]
        self.grid.move_to_top(contact, data["sms"], "sms_recv")


class mainLoop(urwid.MainLoop):

    def __init__(self):
        palette = [("name", "", "", "", "#6dd", ""),
                   ("sms_recv", "", "", "", "#6dd", ""),
                   ("sms_send", "", "", "", "g52", ""),
                   ("bg", "", "", "", "", ""),
                   ("sms_send_query", "", "", "", "#ff0", "")]
        top = urwid.Filler(urwid.Text("waiting phone connection"))
        t = threading.Thread(target=reapp.start_server, args=(self,), daemon=True)
        t.start()
        self.top = None
        notify2.init("sms")
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

    def done(self):
        top = Top(self)
        self.top = top
        self.widget = urwid.AttrMap(top, "bg")
        self.draw_screen()

    def on_recv(self, data):
        n = notify2.Notification("sms", "message receive\n" + data["name"])
        n.show()
        self.top.on_receive(data)
        self.draw_screen()

    def send(self, data):
        pass

    def on_send_confirmation(self, data):
        self.top.send_confirmation(data)
        self.draw_screen()


def main():
    mainloop = mainLoop()
    mainloop.screen.set_terminal_properties(colors=256)
    mainloop.run()
    sys.exit(0)

if __name__ == "__main__":
    main()
