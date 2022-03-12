from discord import Embed, Intents
from discord.ext import commands

import config
from exceptions.exceptions import EntityExistsException, EntityNotFoundException
from model.models import *
from tortoise import run_async

run_async(init_db())

allowedRoles = [
    'tBTC Contributors (Team)',
    'Admin',
    'relay admin',
    ':european_castle: keep team',
    ':european_castle: keep admins',
    'NuCypher Admin'
]

intents = Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!bridge.", help_command=None, intents=intents)


@commands.has_any_role(*allowedRoles)
@bot.command(name='help')
async def relay_help(ctx):
    """
    Function displays list of all available commands for Bridge-Bot
    :param ctx: Discord Context Object
    """
    widget = Embed(description="Available commands for Bridge-Bot", color=0x03D692, title="Bridge-Bot Help")
    widget.add_field(name="!bridge.list", value="The list of groups of relay channels", inline=False)
    widget.add_field(name="!bridge.create_group 'GROUP_NAME'", value="Create new channel group", inline=False)
    widget.add_field(name="!bridge.add GROUP_ID", value="Add current channel to group with following ID", inline=False)
    widget.add_field(name="!bridge.delete", value="Delete relay for the current channel", inline=False)
    widget.add_field(name="!bridge.delete_group GROUP_ID", value="Delete group and all related relays", inline=False)
    # widget.set_thumbnail(url="WHICH LOGO?")
    await ctx.send(embed=widget)


@commands.has_any_role(*allowedRoles)
@bot.command(name='list')
async def relay_list(ctx):
    """
    The function shows a list of groups and linked channels in groups
    :param ctx: Discord Context Object
    """
    widget = Embed(color=0x03D692, title="Channel groups")
    # Get list of all groups
    if not (groups := await Group.all()):
        widget.add_field(name="The list of groups is empty",
                         value="Create new group using `!bridge.create_group 'GROUP_NAME'`", inline=False)
        await ctx.send(embed=widget)
        return

    # Iterate over this group-list and add fields with channels to widget
    for group in groups:
        group_name_id = f"{group.name} [ID {str(group.id)}]:"

        if not (channels := await Channel.filter(group_id=group.id)):
            widget.add_field(name=group_name_id, value="Group is empty", inline=False)
            continue

        channel_list = []
        for i in channels:
            channel = bot.get_channel(i.channel_id)
            channel_list.append(f"{channel.guild.name}[{channel.name}]")

        channel_list = '\n'.join(channel_list)
        widget.add_field(name=group_name_id, value='```' + channel_list + '```', inline=False)
    await ctx.send(embed=widget)


@commands.has_any_role(*allowedRoles)
@bot.command(name='delete')
async def relay_delete(ctx):
    """
    Removes the current channel from the relay group
    :param ctx: Discord Context Object
    """
    # Check if channel exists in database
    if channel := await Channel.get_or_none(channel_id=ctx.message.channel.id):
        await channel.delete()
        # Check if webhook exists for this channel
        if webhook := await bot.fetch_webhook(webhook_id=channel.hook):
            await webhook.delete()
        await ctx.send("Relay successfully deleted🤖")
    else:
        raise EntityNotFoundException("No relays were found for this channel🤖")


@commands.has_any_role(*allowedRoles)
@bot.command(name='delete_group')
async def relay_delete_group(ctx, id_group: int):
    """
    A function that deletes a group of channels, as well as all webhooks created for this group
    :param ctx: Discord Context Object
    :param id_group: Group ID
    """
    # Check if group exists
    if not (group := await Group.get_or_none(id=id_group)):
        raise EntityNotFoundException(f"Group with ID {id_group} does not exist🤖️")

    # Get all channels related to this group
    channels = await Channel.filter(group=id_group)
    # Delete all Relay-webhooks and Channel-entities related to this group
    for channel in channels:
        if webhook := await bot.fetch_webhook(webhook_id=channel.hook):
            await webhook.delete()
        await channel.delete()
    # Delete group
    await group.delete()
    await ctx.send(f"Group with ID {id_group} was successful deleted🤖️")


@commands.has_any_role(*allowedRoles)
@bot.command(name='create_group')
async def relay_create_group(ctx, arg: str):
    """
    A function that creates a group of channels for their subsequent linking
    :param ctx: Discord Context Object
    :param arg: Group name
    """
    # Check if group exists
    if not (group := await Group.get_or_none(name=arg)):
        group = await Group.create(name=arg)
        await ctx.send(f"Group with name {group.name} was succesfully created with ID {group.id}🤖")
    else:
        raise EntityExistsException(f"Group with name {group.name} already exists🤖")


@commands.has_any_role(*allowedRoles)
@bot.command(name='add')
async def relay_add(ctx, id_group: int):
    """
    A function that adds a given channel to a group, thereby creating a relay with all the channels in the group.
    :param ctx: Discord Context Object
    :param id_group: Group ID
    """
    # Get channel Object
    channel = ctx.message.channel
    # Get all channel webhooks
    webhooks = await channel.webhooks()

    # Check if specified group exists
    if not (group := await Group.get_or_none(id=id_group)):
        raise EntityNotFoundException("The specified group does not exist🤖")

    # Check if webhook already exists for this channel
    if any([i.name == "Relay" for i in webhooks]):
        if await group.channels.filter(channel_id=ctx.message.channel.id):
            raise EntityExistsException("Relay already exists🤖")

    # Create webhook
    webhook = await channel.create_webhook(name="Relay", reason="For Bridge-Bot")
    # Create Channel entity and store it in database
    await Channel.create(name=channel.name, guild_id=ctx.message.guild.id, channel_id=ctx.message.channel.id,
                         group_id=id_group, hook=webhook.id)
    await webhook.send('Relay successfully created🤖')


@bot.event
async def on_command_error(ctx, error):
    """
    Custom exception handler
    :param ctx: Discord Context Object
    :param error: Command Error Object
    """
    print(error)
    if isinstance(error, EntityExistsException):
        await ctx.send(error.message)
    elif isinstance(error, EntityNotFoundException):
        await ctx.send(error.message)


@bot.listen('on_message')
async def relay_processor(message):
    """
    A function that forwards messages across all channels in the group.
    The bot takes the user's avatar and nickname and sends a message over the webhook.
    :param message: Discord Message Object
    """
    # Checking that the message is not from a bot, and also that it is not a command
    if message.author.bot is True or message.content.startswith('!relay'):
        return

    # Get User object
    user = bot.get_user(message.author.id)

    # Checking that the current channel is stored in the database, and that it is associated with a particular group
    if channel := await Channel.get_or_none(channel_id=message.channel.id):
        channels = await Channel.filter(group=channel.group_id)
        for i in channels:
            if i.channel_id == message.channel.id:
                continue
            # Get Discord Webhook object
            webhook = await bot.fetch_webhook(i.hook)
            # Collect all attachments from message
            files = [await pp.to_file() for pp in message.attachments]
            # Change bot avatar, username, add all message content and reply message over webhook
            await webhook.send(username=user.name + ' | ' + message.channel.guild.name, content=message.content,
                               avatar_url=user.avatar_url, files=files)


if __name__ == "__main__":
    bot.loop.run_until_complete(Tortoise.init(db_url='sqlite://relays.sqlite3', modules={'models': ['model.models']}))
    bot.run(config.TOKEN)
