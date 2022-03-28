import time
import os

#запуск выбранного элемента
class Start:
    def main(self):
        self.slowType("1 : запуск бота", .02)
        self.slowType("2 : отправка эмбеда (перед запуском отредактируйте embed.py)", .02)
        pick = float(input("\n"))
        if pick == 1:
            os.startfile('main.py')
            os.startfile('sender.py')
            os.startfile('msglogger.py')
        if pick == 2:
            os.startfile('embed.py')

    #метод для медленной печати

    def slowType(self, text, speed, newLine = True):
        for i in text:
            print(i, end = "", flush = True)
            time.sleep(speed)
        if newLine:
            print()

if __name__ == '__main__':
    start = Start()
    start.main()

