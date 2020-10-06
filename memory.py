from enum import Enum
from os import path
from time import time
import os


class FakeFile:
    def __init__(self, fn):
        self.fn = fn

    def seek(self, *args):
        pass

    def close(self):
        pass

    def read(self, *args):
        return b''


class Memory:
    def __init__(self, fn):
        self.show_info = lambda: None
        self.is_fake = not(fn and path.exists(fn))
        self.fo = FakeFile(fn) if self.is_fake else open(fn, 'rb')
        self.blocks = [(0, -1, False)]
        self.fsize = 0 if self.is_fake else os.lseek(self.fo.fileno(), 0, 2)
        self.fn = fn
        self.actions = []
        self.cancels = []
        self.edit = False
        self.undo_actions = {self.remove: self._undo_remove,
                             self.insert: self._undo_insert,
                             self.paste: self._undo_paste,
                             self.cut: self._undo_cut,
                             self.cut_paste: self._undo_cut_paste,
                             self.replace: self._undo_replace}

    def get_data(self, start, n):
        k, i = self._get_n_block(start)
        result = self._get_block_data(i, n, start-k)
        while len(result) != n and self.blocks[i][1] != -1:
            i += 1
            result += self._get_block_data(i, n-len(result))
        return result

    def cut(self, area):
        s, e = (min(area), max(area))
        data = []
        for i in range(s, e):
            data.append(self.remove(s))
            self.actions.pop()
        self.actions.append((self.cut, s, data))
        self.cancels = []
        return bytes(data)

    def paste(self, pos, data):
        area = (pos, pos+len(data))
        for e in data:
            self.insert(pos, e // 16)
            self.insert(pos, e % 16)
            pos += 1
            self.actions.pop()
        self.actions.append((self.paste, area))
        self.cancels = []

    def cut_paste(self, area, data):
        prev_data = self.cut(area)
        self.paste(min(area), data)
        self.actions.pop()
        self.actions.pop()
        area = (min(area), min(area)+len(data))
        self.actions.append((self.cut_paste, area, prev_data))
        self.cancels = []
        return prev_data

    def insert(self, pos, elem):
        if not self.edit:
            self.fsize += 1
            self.actions.append((self.insert, pos))
            self.cancels = []
        self._insert(pos, elem)
        self.edit = not self.edit

    def remove(self, pos):
        if pos < self.fsize:
            self.fsize -= 1
            elem = self._remove(pos)
            self.actions.append((self.remove, pos, elem))
            self.cancels = []
            self.edit = False
            return elem

    def replace(self, pos, elem):
        pr_el = None
        if not self.edit:
            pr_el = self.remove(pos)
            action = (self.insert, pos)
            if pr_el != None:
                action = (self.replace, pos, pr_el)
                self.actions.pop()
            self.actions.append(action)
        self.insert(pos, elem)
        if self.edit:
            self.actions.pop()
        return pr_el

    def undo(self):
        if self.actions:
            action = self.actions.pop()
            c = self.cancels
            cancel = self.undo_actions[action[0]](action[1:])
            self.actions.pop()
            self.cancels = c
            self.cancels.append(cancel)

    def redo(self):
        if self.cancels:
            self.edit = False
            action = self.cancels.pop()
            c = self.cancels
            if action[0] in [self.insert, self.replace]:
                action[0](action[1], action[2] // 16)
                action[0](action[1], action[2] % 16)
            else:
                action[0](*action[1:])
            self.cancels = c

    def save(self, name=None):
        name, save_funk = self._prep_for_save(name)
        self.time = time()
        with open(name, 'rb+') as fo:
            while self.blocks:
                if save_funk(self.blocks.pop(0), fo):
                    return
            try:
                fo.truncate(self.fp)
            except Exception:
                pass

# -------------------------------------------------------------------- #

    def _undo_insert(self, action):
        elem = self.remove(*action)
        return (self.insert, action[0], elem)

    def _undo_remove(self, action):
        self.insert(action[0], action[1] // 16)
        self.insert(action[0], action[1] % 16)
        return (self.remove, action[0])

    def _undo_replace(self, action):
        elem = self.replace(action[0], action[1] // 16)
        self.replace(action[0], action[1] % 16)
        return (self.replace, action[0], elem)

    def _undo_cut(self, action):
        self.paste(*action)
        return (self.cut, (action[0], action[0]+len(action[1])))

    def _undo_paste(self, action):
        data = self.cut(*action)
        return (self.paste, min(action[0]), data)

    def _undo_cut_paste(self, action):
        data = self.cut_paste(*action)
        area = (min(action[0]), min(action[0])+len(action[1]))
        return (self.cut_paste, area, data)

    def _insert(self, pos, elem):
        counter, i = self._get_n_block(pos)
        block = self.blocks.pop(i)
        pos -= counter
        blocks = []
        if block[2]:
            if self.edit:
                block[3][pos] += elem
                blocks.append(block)
            else:
                block[3].insert(pos, elem*16)
                blocks.append((block[0], len(block[3]), block[2], block[3]))
        else:
            start = block[0] + pos
            elem *= 16
            if pos:
                blocks.append((block[0], pos, False))
            blocks.append((start, 1, True, [elem]))
            blocks.append((start, block[1]-pos if block[1] > 0 else -1, False))
        for k in range(len(blocks)):
            self.blocks.insert(i+k, blocks[k])

    def _remove(self, pos):
        k, i = self._get_n_block(pos)
        pos -= k
        if self.blocks[i][2] and len(self.blocks[i][3]) <= pos:
            pos -= self.blocks[i][1]
            i += 1
        blocks = []
        block = self.blocks.pop(i)
        if block[2]:
            elem = block[3].pop(pos)
            if len(block[3]):
                blocks.append((block[0], len(block[3]), True, block[3]))
        else:
            _len = block[1] if block[1] < 0 else block[1] - (pos + 1)
            if pos:
                blocks.append((block[0], pos, False))
            self.fo.seek(block[0]+pos)
            elem = self.fo.read(1)[0]
            if _len:
                blocks.append((block[0]+pos+1, _len, False))
        for l in range(len(blocks)):
            self.blocks.insert(i+l, blocks[l])
        return elem

    def _prep_for_save(self, name):
        if name:
            with open(name, 'wb') as fo:
                funk = self._save_as
                self.fo.seek(0)
        else:
            funk = self._save
            name = self.fn
            self.fo.close()
        self.fp = 0
        self.ifp = 0
        self.data = b''
        self.prev_fp = 0
        return (name, funk)

    def _save_as(self, block, fo):
        if block[2]:
            self.fp += fo.write(bytes(block[3]))
        else:
            self._rewrite(block[0], block[1], self.fo, fo)

    def _save(self, block, fo):
        if block[2]:
            fo.seek(max(self.fp, block[0]))
            self.data += fo.read(block[1])
            fo.seek(self.fp)
            self.fp += fo.write(bytes(block[3]))
        else:
            self.data = self.data[block[0]-self.ifp:]
            if not self.data and self.fp == block[0]:
                if block[1] == -1:
                    return True
                self.fp += block[1]
            else:
                self._rewrite(block[0], block[1], fo, fo)
            self.ifp = block[0] + block[1]

    def _rewrite(self, start, size, foi, foo):
        data = b'1'
        while size if size > -1 else data:
            foi.seek(max(self.fp, start))
            _len = min(size, 1024) if size > -1 else 1024
            self.data += foi.read(_len)
            foo.seek(self.fp)
            delta = foo.write(self.data[:_len])
            size -= delta
            start += delta
            self.fp += delta
            data = self.data
            self.data = self.data[_len:]
            t = time()
            if t - self.time > 1:
                self.time = t
                speed = (self.fp - self.prev_fp) // 0x100000
                rem_time = (self.fsize - self.fp) // (self.fp - self.prev_fp)
                self.prev_fp = self.fp
                loaded_msg = "Writen {} Mb".format(self.fp // 0x100000)
                speed_msg = "Speed {} Mb/s".format(speed)
                remaining = "Remaining time {}".format(rem_time)
                self.show_info(loaded_msg, speed_msg, remaining)

    def _get_n_block(self, pos):
        counter = 0
        i = 0
        for block in self.blocks:
            if block[1] < 0:
                break
            next_counter = counter + block[1]
            if pos >= next_counter:
                if pos == next_counter and block[2]:
                    break
                counter = next_counter
                i += 1
            else:
                break
        return (counter, i)

    def _get_block_data(self, n, max_count, start=0):
        if self.blocks[n][2]:
            return self.blocks[n][3][start:start+max_count]
        self.fo.seek(self.blocks[n][0]+start)
        k = max_count if self.blocks[n][1] < 0 else self.blocks[n][1]-start
        return list(self.fo.read(min(max_count, k)))
