import os
import math
import curses
from creator import Creator


class Console:
    def __init__(self, manipulator):
        curses.initscr()
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_WHITE)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLUE)
        curses.curs_set(False)
        curses.noecho()
        curses.raw()
        self.ext_data = ""
        self.pad = curses.newwin(0, 0, 0, 0)
        self.pad.nodelay(False)
        self.lr = 16
        self.lm = 1 + (self.lr + 4) * 3
        self.source = manipulator

    def show_info(self, header, *lines):
        lines = list(lines)
        lines.append(header)
        length = max(list(map(len, lines)))+2
        window = curses.newwin(len(lines)+2, length, 0, 0)
        window.addstr(1, 1, lines.pop())
        for i in range(len(lines)):
            window.addstr(i+2, 1, lines.pop())
        window.border()
        window.refresh()
        return window

    def message(self, string, *line):
        window = self.show_info(string, *line)
        key = self.get_key(False)
        window.clear()
        window.refresh()
        return key

    def get_number(self, message="Set byte"):
        char = b''
        num = ""
        while char != '\n':
            char = self.message(message, num).decode('latin-1')
            start_hex = char in "x" and num == "0"
            is_hexed = num[:2] == "0x" and char in "abcdefABCDEF"
            if char.isdigit() or start_hex or is_hexed:
                num += char
            elif char.encode() == b'\x7f':
                num = num[:-1]
        return num

    def get_name(self, header):
        char = b''
        name = []
        while char != b'\n':
            char = self.message(header, "".join(name))
            if char.decode().isprintable():
                name.append(char.decode())
            elif char == b'\x7f':
                name.pop()
        return "".join(name)

    def get_key(self, isnt_msg=True):
        substitutions = {b'\r': b'\n', b'\x08': b'\x7f', b'ic': b'\x1b[A',
                         b'kc': b'\x1b[B', b'lc': b'\x1b[C', b'jc': b'\x1b[D',
                         b'\x04': b'\x1b[3~', b'\x1b[4~': b'\x1b[F',
                         b'\x1b[1~': b'\x1b[H', b'Jc': b'\x1b[1;2D',
                         b'Kc': b'\x1b[1;2B', b'Lc': b'\x1b[1;2C',
                         b'Ic': b'\x1b[1;2A'}
        key = self._get_key()
        should_substituded = key in 'ijklIJKL'
        if self.source.main and isnt_msg and should_substituded:
            key += 'c'
        key = key.encode()
        if key in substitutions:
            key = substitutions[key]
        return key

    def update(self):
        self.source.check()
        self.columns, self.rows = os.get_terminal_size()
        self.rows -= 2
        self._copy_data()
        y = min(self.cursor[0], self.rows)
        curs = (self._set_y_loc(y), self.cursor[1])
        lc = len(self.creator.lines)
        self.source.update(curs, self.rows, lc)
        self._drawing_on_pad()
        self._paint_sel_area()
        self._set_correct_cursor()
        self.pad.refresh()

    def exit(self):
        quest = "Do you want to save?(y/N)"
        curses.endwin()
        curses.curs_set(True)
        curses.echo()

# ---------------------------------------------------------------------#

    def _copy_data(self):
        self.mem = self.source.mem
        self.win_y_loc = self.source.win_y_loc
        self.cursor = self.source.cursor
        self.mode = self.source.mode
        self.main = self.source.main

    def _set_y_loc(self, y):
        while True:
            self.win_y_loc = self.source.win_y_loc
            invisible = self.win_y_loc*self.lr
            block = self.mem.get_data(invisible, self.rows*self.lr)
            self.creator = Creator(block, self.lr, self.win_y_loc)
            if len(self.creator.lines) > self.rows-2 or not self.win_y_loc:
                break
            y += 1
            self.source.win_y_loc -= 1
        return y

    def _paint_sel_area(self):
        if self.source.selected_area:
            s, e = self.source.selected_area
            s, e = (max(self.win_y_loc*self.lr, min(s, e)),
                    min((self.win_y_loc+self.rows)*self.lr, max(s, e)))
            s -= self.win_y_loc*self.lr
            e -= self.win_y_loc*self.lr
            for i in range(s, e):
                y, x = self.source.set_cursor(i, False)
                self.pad.chgat(y+1, x*3+12, 2, curses.color_pair(4))
                self.pad.chgat(y+1, x+self.lm+1, 1, curses.color_pair(4))

    def _set_correct_cursor(self):
        y, x = self.source.cursor
        x, count = (x*3+12, 2) if self.main else (x+self.lm+1, 1)
        self.pad.chgat(y+1, x, count, curses.color_pair(2))

    def _get_key(self):
        key = self.pad.getkey().encode()
        if key == b'\x1b':
            key += self.pad.getkey().encode()
            if b'['[0] == key[-1]:
                key += self.pad.getkey().encode()
                if key[-1] in range(48, 59):
                    key += self.pad.getkey().encode()
                    if b';'[0] == key[-1]:
                        key += self.pad.getkey().encode()
                        if key[-1] in range(48, 59):
                            key += self.pad.getkey().encode()
        return key.decode()

    def _drawing_on_pad(self):
        len_l = len(self.creator.lines)
        for i in range(self.rows):
            n = self.creator.lines[i] if i < len_l else " "*(self.lm+self.lr+1)
            self.pad.addstr(i+2, 0, n, curses.color_pair(1))
        header = "{}    {} {}".format(self.mem.fn, self.mode, self.ext_data)
        numbers = ["{}   ".format("x"*8)]
        nums = ""
        for i in range(self.lr):
            numbers.append("0{} ".format(hex(i)[2]))
            nums += hex(i)[2]
        numbers.append("  {}".format(nums))
        self.pad.addstr(0, 0, " " * (self.columns+1), curses.color_pair(3))
        self.pad.addstr(0, 1, header, curses.color_pair(3))
        self.pad.addstr(1, 1, "".join(numbers), curses.color_pair(1))
