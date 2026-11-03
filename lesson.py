"""Data types for lessons. A lesson is just a list of Steps; each Step has optional Tasks."""


class Task:
    def __init__(self, label, check, say=None, expr=None, want=None, bar=False):
        self.label = label      # shown in the task card ({orbit}-style key placeholders allowed)
        self.check = check      # fn(rt) -> bool or 0..1 progress
        self.say = say          # line the bot says when this task becomes current (not for the first task)
        self.expr = expr
        self.want = want        # object name (or 'bot') this task wants selected: wrong picks get a reaction
        self.bar = bar          # show a progress bar


class Step:
    def __init__(self, id, title, say, tasks=(), success=None, hint=None, setup=None,
                 teach=(), expr='idle', tags=()):
        self.id = id
        self.title = title
        self.say = say
        self.tasks = list(tasks)
        self.success = success
        self.hint = hint
        self.setup = setup
        self.teach = list(teach)  # [(action, key-id or literal)] added to the cheat sheet on completion
        self.expr = expr
        self.tags = set(tags)


class Lesson:
    def __init__(self, id, name, description, steps):
        self.id = id
        self.name = name
        self.description = description
        self.steps = steps
