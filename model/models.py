from tortoise.models import Model
from tortoise import fields, run_async
from tortoise import Tortoise


class Group(Model):
    name = fields.CharField(max_length=255)
    channels: fields.ReverseRelation["Channel"]

    def __str__(self):
        return self.name


class Channel(Model):
    name = fields.CharField(max_length=255)
    guild_id = fields.BigIntField(unique=False)
    channel_id = fields.BigIntField(unique=True)
    group: fields.ForeignKeyRelation[Group] = fields.ForeignKeyField(
        "models.Group", related_name="channels"
    )
    hook = fields.BigIntField(unique=True)

    def __str__(self):
        return self.name


async def init_db():
    # Here we create a SQLite DB using file "db.sqlite3"
    #  also specify the app name of "models"
    #  which contain models from "app.models"
    await Tortoise.init(
        db_url='sqlite://relays.sqlite3',
        modules={'models': ['model.models']}
    )
    # Generate the schema
    await Tortoise.generate_schemas(safe=True)
