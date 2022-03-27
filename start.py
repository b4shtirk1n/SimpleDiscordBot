import time
import os

class start:
    def main(self):
        self.slowType("1 : запуск бота", .02)
        self.slowType("2 : отправка эмбеда", .02)
        pick = float(input("\n"))
        if pick == 1:
            os.startfile('main.py')
            os.startfile('sender.py')
            os.startfile('msglogger.py')
        if pick == 2:
            os.startfile('embed.py')

    def slowType(self, text, speed, newLine = True):
        for i in text:
            print(i, end = "", flush = True)
            time.sleep(speed)
        if newLine:
            print()

