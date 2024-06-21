from threading import Lock as Mutex
from contest_import import Contest, Row
import time
from sheets import load_to_sheets

TASK_COST = 100

class Bet:
    def __init__(self, money, task):
        self.money = money
        self.task = task
        self.coef = 2.0
        self.unique_id = time.time()

    def __str__(self):
        return f"Bet({self.money}, {self.task})"

class Team:

    def __init__(self, name, budget = 0, bets = set(), line = Row()):
        self.name = name 
        self.budget = budget 
        self.bets = bets
        self.line = line

    def __str__(self):
        return f"Team(\"{self.name}\", {self.budget}, {str(self.bets)}, {str(self.line)})"

    def add_money(self, add):
        self.budget += add

    def have_bets(self) -> bool:
        return len(self.bets) > 0

    def make_bet(self, money, task):
        if (money >  self.budget):
            return False        # Слишком много хотите

        # Допустимо делать несколько ставок на одну задачу
        # Фактически, это одна ставка с увеличенной стоимостью

        if (self.line.tasks == None or self.line.tasks[task] == 0):
            self.bets.add(Bet(money, task))
            self.budget -= money
            return True

    def get_budget(self):
        return self.budget
    
    def get_unsolveed_tasks(self):
        ans = []
        for task_name, code in self.line.tasks.items():
            if (code == 0):
                ans.append(task_name)
        ans.sort()
        return ans

    def update(self, line:Row):
        global TASK_COST
        to_delete = set()
        for bet in self.bets:
            nw = line.tasks[bet.task]
            if (nw >= 1): 
                self.budget += bet.money * bet.coef
            if (nw != 0):
                to_delete.add(bet)
        
        for elem in to_delete:
            self.bets.discard(elem)

        for task_name, new_res in line.tasks.items():
            old_res = 0
            if task_name in self.line.tasks.keys():
                old_res = self.line.tasks[task_name]
            
            if (old_res <= 0 < new_res):
                self.budget += TASK_COST

        self.line = line

class DataBase: 
    def __init__(self, team_by_id_file, contest_id):
        self.contest = Contest(contest_id)
    
        self._registrated_users = {}
        self.mutex_reg_users = Mutex()

        self._on_registration = set()
        self.mutex_on_reg = Mutex()

        self._team_by_id = {}
        self.mutex_team = Mutex()

        self.teams = []
        
        self._team_obj_by_name = {}
        self.mutex_team_obj = Mutex()

        self._registrating_task = {}
        self.mutex_reg_task = Mutex()
        try: 
            with open(team_by_id_file, 'r') as file:
                dct = file.read()
                exec(f"self._team_by_id = {dct}")

            for reg_code, team_name in self._team_by_id.items():
                self.teams.append(team_name)
                self._team_obj_by_name[team_name] = Team(team_name)
        
        except Exception as e:
            print("Cant read registration file. It should be in print(dict()) form")
            print(e)

    def user_choosed_task(self, tg_id : str, task_name : str) -> None:
        self.mutex_reg_task.acquire()
        self._registrating_task[tg_id] = task_name
        self.mutex_reg_task.release()

    def task_chosen_for_bet(self, tg_id : str) -> str:
        self.mutex_reg_task.acquire()
        res = None
        if tg_id in self._registrating_task.keys():
            res = self._registrating_task[tg_id]
        self.mutex_reg_task.release();
        return res

    def bet_has_been_approved(self, tg_id : str) -> None:
        self.mutex_reg_task.acquire()
        self._registrating_task[tg_id] = None
        self.mutex_reg_task.release()
        
    def update(self):
        self.mutex_team_obj.acquire()
        table = self.contest.get_table()

        for name, row in table.items():
            if name in self._team_obj_by_name.keys():
                self._team_obj_by_name[name].update(row)
            else:
                self._team_obj_by_name[name] = Team(name)
                self._team_obj_by_name[name].update(row)
                
        self.mutex_team_obj.release()

    def team_obj_by_name(self, name:str) -> Team:
        self.mutex_team_obj.acquire()
        res = self._team_obj_by_name[name]
        self.mutex_team_obj.release()
        return res

    def team_name_by_id(self, id : str) -> str:
        self.mutex_team.acquire()
        res = self._team_by_id[id]
        self.mutex_team.release()
        return res
    
    def in_registration_queue(self, tg_id : str) -> bool:
        self.mutex_on_reg.acquire()
        res = tg_id in self._on_registration
        self.mutex_on_reg.release()
        return res

    def add_in_reg_queue(self, tg_id):
        self.mutex_on_reg.acquire()
        self._on_registration.add(tg_id)
        self.mutex_on_reg.release()
        
    def registrate(self, tg_id : str, team_tag : str) -> bool:
        self.mutex_team.acquire()
        if not (team_tag in self._team_by_id.keys()):
            self.mutex_team.release()
            return False
        
        self.mutex_reg_users.acquire()
        self._registrated_users[tg_id] = self._team_by_id[team_tag]
        self.mutex_team.release()
        self.mutex_reg_users.release()

        self.mutex_on_reg.acquire()
        self._on_registration.discard(tg_id)
        self.mutex_on_reg.release()
        return True

    def team_of(self, tg_id : str) -> str:
        self.mutex_team.acquire();
        res = self._registrated_users[tg_id];
        self.mutex_team.release()
        return res

    def is_registrated_user(self, tg_id : str) -> bool:
        self.mutex_reg_users.acquire()
        res = tg_id in self._registrated_users.keys()
        self.mutex_reg_users.release()
        return res
    
    def save(self, path = "database.save"):
        with open(path, 'w') as file:
            #file.write(str(self._team_obj_by_name)+'\n')
            ans = []
            for name, obj in self._team_obj_by_name.items():
                ans.append(f"\"{name}\" : {str(obj)}")
            ans = "{" + ", ".join(ans) + "}"
            file.write(ans + "\n")
            file.write("SEPARATOR\n")
            file.write(str(self._registrated_users)+'\n')
            file.write("SEPARATOR\n")
            file.write(str(self._registrating_task)+'\n')
            file.write("SEPARATOR\n")
            file.write(str(self._team_by_id)+'\n')
            file.write("SEPARATOR\n")
            file.write(str(self._on_registration)+'\n')

    def load(self, path = "database.save"):
        with open(path, 'r') as file:
            dicts = file.read().split("SEPARATOR\n")
            exec(f"self._team_obj_by_name = {dicts[0]}")
            exec(f"self._registrated_users = {dicts[1]}")
            exec(f"self._registrating_task = {dicts[2]}")
            exec(f"self._team_by_id = {dicts[3]}")
            exec(f"self._on_registration = {dicts[4]}")
        
    def save_table_to_csv(self, path="table_budget.csv"):
        table = []
        script = ["Название команды", "Баллы", "Решено"] + [task_name for task_name in self.contest.task_names]

        for name in self.teams:
            team = self.team_obj_by_name(name)
            table.append([team.name, str(team.budget), str(team.line.solved)] + [str(team.line.tasks[task_name]) for task_name in self.contest.task_names])
        table.sort(key= lambda a : -int(a[1]))
        
        with open(path, "w") as file:
            file.write(", ".join(script) + "\n")
            for line in table:
                file.write(", ".join(line) + "\n")
    
    def parralel_update_sycle(self):
        while(1):
            print("DB is updating")
            self.update()
            self.save_table_to_csv("standings_with_budget.csv")
            load_to_sheets(csv_data = "standings_with_budget.csv")
            self.save("bot_DB_state.save")
            time.sleep(10)
            
            