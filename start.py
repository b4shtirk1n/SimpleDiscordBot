import time
import os

#запуск выбранного элемента
class Start:
    def main(self):
        self.slowType("1 : запуск бота", .02)
        self.slowType("2 : отправка эмбеда (перед запуском отредактируйте embed.py)", .02)
        pick = float(input("\n"))
        if pick == 1:
            subprocess.call(["start", "python", "main.py"], shell=True)
            subprocess.call(["start", "python", "sender.py"], shell=True)
            subprocess.call(["start", "python", "msglogger.py"], shell=True)
        if pick == 2:
            subprocess.call(["start", "python", "embed.py"], shell=True)

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

