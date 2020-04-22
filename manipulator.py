from enum import Enum
from memory import Memory
from creator import Creator
from os import path


class Mode(Enum):
    edit = "Edit"
    append = "Append"


class Manipulator:
    def __init__(self, fn):
        self.main = True
        self.mode = Mode.edit
        self.mem = Memory(fn)
        self.cursor = (1, 0)
        self.win_y_loc = 0
        self.lr = 16
        self.height = 4
        self.selected_area = None
        self.buffer = b''

    def update(self, cursor, height, lc):
        self.cursor = cursor
        self.height = height
        self.lc = lc
        self.check()

    def open(self, name):
        if name:
            info = self.mem.show_info
            self.mem = Memory(name)
            self.mem.show_info = info

    def sel_l(self):
        self._select_and_act(self.ml_cursor)

    def sel_d(self):
        self._select_and_act(self.md_cursor)

    def sel_u(self):
        self._select_and_act(self.mu_cursor)

    def sel_r(self):
        self._select_and_act(self.mr_cursor)

    def cut(self):
        self.buffer = self._del_area()

    def copy(self):
        if self.selected_area:
            s, e = self.selected_area
            self.buffer = bytes(self.mem.get_data(min(s, e), abs(e-s)))

    def paste(self):
        if self.buffer:
            if self.selected_area:
                self.mem.cut_paste(self.selected_area, self.buffer)
                self.go(min(self.selected_area)+len(self.buffer))
            else:
                self.mem.paste(self.get_cp(), self.buffer)
                self.go(self.get_cp()+len(self.buffer))

    def check(self):
        if self.get_cp() > self.mem.fsize:
            self.go(self.mem.fsize)

    def md_cursor(self):
        y, x = self.cursor
        if y == self.height:
            self.win_y_loc += 1
            self.check()
            return
        self.cursor = (y+1, x)
        self.check()

    def mu_cursor(self):
        y, x = self.cursor
        if y == 1:
            if self.win_y_loc == 0:
                self.set_cursor(0)
            else:
                self.win_y_loc -= 1
            return
        self.cursor = (y-1, x)

    def ml_cursor(self):
        y, x = self.cursor
        if x == 0:
            self.cursor = (y, self.lr-1)
            self.mu_cursor()
        else:
            self.cursor = (y, x-1)

    def mr_cursor(self):
        y, x = self.cursor
        if x == self.lr-1:
            self.cursor = (y, 0)
            self.md_cursor()
        else:
            self.cursor = (y, x+1)
        self.check()

    def go_end(self):
        self.go(self.mem.fsize)

    def go_begin(self):
        self.go(0)

    def get_cp(self):
        row = self.win_y_loc + self.cursor[0] - 1
        return self.lr * row + self.cursor[1]

    def next_page(self):
        self.win_y_loc += self.height

    def prev_page(self):
        if self.win_y_loc:
            self.win_y_loc = max(self.win_y_loc - self.height, 0)
        else:
            self.go(0)

    def replace(self, elem):
        self.mem.replace(self.get_cp(), elem)

    def insert(self, elem):
        self.mem.insert(self.get_cp(), elem)

    def delete(self):
        if self.selected_area:
            self._del_area()
        else:
            self.mem.remove(self.get_cp())

    def redo(self):
        self.mem.redo()

    def undo(self):
        self.mem.undo()

    def backspase(self):
        if self.get_cp():
            self.ml_cursor()
            self.delete()
        elif self.selected_area:
            self.delete()

    def set_cursor(self, t, quet=True):
        x = t % self.lr
        y = t // self.lr + 1
        if quet:
            self.cursor = (y, x)
        else:
            return (y, x)

    def go(self, num):
        if num > self.mem.fsize:
            num = self.mem.fsize
        y, x = self.cursor
        num -= self.get_cp()
        x = num % self.lr + x % self.lr
        y += num // self.lr + x // self.lr
        if y < 1:
            self.win_y_loc += y - 1
            y = 1
        elif y > self.height:
            self.win_y_loc += y + 1 - self.height
            y = self.height - 1
        self.cursor = (y, x % self.lr)

    def set_mode(self, _mode):
        self.mode = _mode
        self.update()

    def change_window(self):
        self.main = not self.main

    def change_mode(self):
        if self.mode == Mode.edit:
            self.mode = Mode.append
        elif self.mode == Mode.append:
            self.mode = Mode.edit

    def save(self, name=None):
        blocks = self.mem.blocks
        info = self.mem.show_info
        try:
            self.mem.save(name)
            if not name:
                name = self.mem.fn
            self.open(name)
        except Exception as e:
            self.open(self.mem.fn)
            self.mem.show_info = info
            self.mem.blocks = blocks
            raise

    def exit(self):
        if self.mem.fn and path.exists(self.mem.fn):
            self.mem.fo.close()

# -------------------------------------------------------------------- #

    def _select_and_act(self, func):
        start = self.selected_area[0] if self.selected_area else self.get_cp()
        if start > self.mem.fsize:
            start = self.mem.fsize
        func()
        end = self.get_cp()
        self.selected_area = None if start == end else (start, end)

    def _del_area(self):
        if self.selected_area:
            buff = self.mem.cut(self.selected_area)
            self.go(min(self.selected_area))
            return buff
        return b''
