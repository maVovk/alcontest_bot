import requests 
import time 
from bs4 import BeautifulSoup
from threading import Lock as Mutex

class Row:
    def __init__(self, team="", tasks=[], solved=0, penalty=0, task_names=[]):
        self.team = team
        self.solved = int(solved)
        self.penalty = int(penalty)
        self.tasks = {}
        for num, score in enumerate(tasks):
            res = score
            if (res == '-'):
                res = '-0'
            elif (res == "+"):
                res = '1'
            self.tasks[task_names[num]] = int(res)

    def empty(self):
        return self.team == None  

    def __str__(self):

        score = sorted([(key, value) for key, value in self.tasks.items()])
        tasks = [str(a[1]) for a in score]
        name = self.team.strip("\"\' ")
        return f"Row(\"{name}\", {self.tasks}, {self.solved}, {self.penalty}, {tasks})"
     
    def to_print(self):
        score = sorted([(key, value) for key, value in self.tasks.items()])
        tasks = ','.join([str(a[1]) for a in score])
        name = self.team.strip("\"\' ")
        return f"{name}, {tasks}, {self.solved}, {self.penalty}"


# https://official.contest.yandex.ru/contest/62780/answers/?p=3
class Contest:
    def __init__ (self, contest_id : str):

        # Я не нашел какого-то номральног api, поэтому мы будем заходить в контест под 
        # логином одного из участников и выкачивать таблицу. 
        self.table_link = f"https://official.contest.yandex.ru/contest/{contest_id}/standings/"
        self.timing = 0
        self.task_names = []
        self.table = {}
        self.tm_mutex = Mutex()

    def __parse_table(self, text):
        bs = BeautifulSoup(text, "html.parser")

        head = bs.find_all("thead")
        heads = BeautifulSoup(str(head), "html.parser").find_all("th")[2:-2]
        tasks = []
        for i in heads:
            task = str(i.span)[:-7].split('>')[-1]
            tasks.append(task)
        self.task_names = tasks   
        
        body = bs.find_all("tbody")        
        bd = BeautifulSoup(str(body[0]), "html.parser")
        lines = bd.find_all("tr")

        for parti in lines:
            rank = parti.find('td')['title']
            name = parti.find("div")['title'].strip('"')
            data = []
            for task in parti.find_all("td")[2:]:
                task_state = task.find('div')
                if (task_state):
                    string = str(task.find('div'))
                    string = string[:-6].split('>')[-1]
                    data.append(string.replace('—', '-'))
                else:
                    data.append(task['title'])
            self.table[name] = Row(name, data[:-2], data[-2], data[-1], self.task_names)
                
    def __load_table(self):
        for page in range(1,6):
            rq = requests.get(self.table_link + f"?p={page}")
            if (rq.status_code != 200):
                raise ConnectionRefusedError ("Cant reach conteset")
            self.__parse_table(rq.text)

    def get_table(self) -> dict:
        self.tm_mutex.acquire()
        if (time.time() - self.timing > 10):
            self.timing = time.time()
            self.tm_mutex.release()
            self.__load_table()
        else:
            self.tm_mutex.release()
            print("too short time")
        return self.table
    
    def save(self):
        with open("table.csv", "w") as file:
            file.write(f"Имя, {','.join(self.task_names)}, Решено, Штраф\n")
            for name, data in self.table.items():
                file.write(data.to_print() + "\n")

