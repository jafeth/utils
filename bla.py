import random


class Woei(object):
    def __init__(self):
        self.foo = 'x'
        self._bar = None

    @property
    def bar(self):
        if self._bar is None:
            self._bar = random.random()
        return self._bar

    @bar.deleter
    def bar(self):
        self._bar = None


def main():
    x = Woei()
    print(x.bar)
    print(x.bar)
    del x.bar
    print(x.bar)


main()
