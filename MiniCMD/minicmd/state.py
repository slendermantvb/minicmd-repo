class MiniCMDState:
    def __init__(self, username='admin'):
        self.username = username
        self.cwd = ''
        self.sudo = False
        self.history = []
        self.running = True
