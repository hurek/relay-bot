from discord.ext import commands


class EntityExistsException(commands.CommandError):
    def __init__(self, message, *args, **kwargs):
        self.message = message
        super().__init__(*args, **kwargs)


class EntityNotFoundException(commands.CommandError):
    def __init__(self, message, *args, **kwargs):
        self.message = message
        super().__init__(*args, **kwargs)
