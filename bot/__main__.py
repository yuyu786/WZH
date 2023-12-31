#!/usr/bin/env python3
import platform
from time import time
from datetime import datetime
from sys import executable
from os import execl as osexecl
from asyncio import create_subprocess_exec, gather
from uuid import uuid4
from base64 import b64decode
from quoters import Quote
from html import escape

from requests import get as rget
from pytz import timezone
from bs4 import BeautifulSoup
from signal import signal, SIGINT
from aiofiles.os import path as aiopath, remove as aioremove
from aiofiles import open as aiopen
from psutil import disk_usage, cpu_percent, swap_memory, cpu_count, cpu_freq, virtual_memory, net_io_counters, boot_time
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, private, regex
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot import bot, config_dict, user_data, botStartTime, LOGGER, Interval, DATABASE_URL, QbInterval, INCOMPLETE_TASK_NOTIFIER, scheduler, bot_name
from .helper.ext_utils.fs_utils import start_cleanup, clean_all, exit_clean_up
from .helper.ext_utils.bot_utils import get_progress_bar_string, get_readable_file_size, get_readable_time, cmd_exec, sync_to_async, set_commands, update_user_ldata, new_thread, format_validity_time, new_task
from .helper.ext_utils.db_handler import DbManger
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.message_utils import sendMessage, editMessage, sendFile, deleteMessage, one_minute_del
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.button_build import ButtonMaker
from .helper.listeners.aria2_listener import start_aria2_listener
from .helper.themes import BotTheme
from .modules import authorize, clone, gd_count, gd_delete, gd_list, cancel_mirror, mirror_leech, status, torrent_search, torrent_select, ytdlp, rss, shell, eval, users_settings, bot_settings, speedtest, save_msg, images, anilist, mediainfo, mydramalist, broadcast, gen_pyro_sess, gd_clean

@new_task
async def stats(client, message):
    if await aiopath.exists('.git'):
        last_commit = (await cmd_exec("git log -1 --pretty='%cd ( %cr )' --date=format-local:'%d/%m/%Y'", True))[0]
        changelog = (await cmd_exec("git log -1 --pretty=format:'<code>%s</code> <b>By</b> %an'", True))[0]
    else:
        last_commit = 'No Data'
        changelog = 'N/A'
    total, used, free, disk = disk_usage('/')
    swap = swap_memory()
    memory = virtual_memory()
    cpuUsage = cpu_percent(interval=0.5)
    stats = BotTheme('STATS',
                     last_commit=last_commit,
                     commit_details=changelog,
                     bot_version=(),
                     bot_uptime=get_readable_time(time() - botStartTime),
                     os_uptime=get_readable_time(time() - boot_time()),
                     os_arch=f"{platform.system()}, {platform.release()}, {platform.machine()}",
                     cpu=cpuUsage,
                     cpu_bar=get_progress_bar_string(cpuUsage),
                     cpu_freq=f"{cpu_freq(percpu=False).current / 1000:.2f} GHz" if cpu_freq() else "Access Denied",
                     p_core=cpu_count(logical=False),
                     v_core=cpu_count(logical=True) - cpu_count(logical=False),
                     total_core=cpu_count(logical=True),
                     ram_bar=get_progress_bar_string(memory.percent),
                     ram=memory.percent,
                     ram_u=get_readable_file_size(memory.used),
                     ram_f=get_readable_file_size(memory.available),
                     ram_t=get_readable_file_size(memory.total),
                     swap_bar=get_progress_bar_string(swap.percent),
                     swap=swap.percent,
                     swap_u=get_readable_file_size(swap.used),
                     swap_f=get_readable_file_size(swap.free),
                     swap_t=get_readable_file_size(swap.total),
                     disk=disk,
                     disk_bar=get_progress_bar_string(disk),
                     disk_t=get_readable_file_size(total),
                     disk_u=get_readable_file_size(used),
                     disk_f=get_readable_file_size(free),
                     up_data=get_readable_file_size(
                         net_io_counters().bytes_sent),
                     dl_data=get_readable_file_size(
                         net_io_counters().bytes_recv)
                     )
    await sendMessage(message, stats, photo='IMAGES')
    
@new_thread
async def start(client, message):
    buttons = ButtonMaker()
    reply_markup = buttons.build_menu(2)
    if len(message.command) > 1 and message.command[1] == "wzmlx":
        await message.delete()
    elif len(message.command) > 1 and config_dict['TOKEN_TIMEOUT']:
        userid = message.from_user.id
        encrypted_url = message.command[1]
        input_token, pre_uid = (b64decode(encrypted_url.encode()).decode()).split('&&')
        if int(pre_uid) != userid:
            return await sendMessage(message, '<b>This token is not for you!</b>\n\nPlease generate your own.')
        data = user_data.get(userid, {})
        if 'token' not in data or data['token'] != input_token:
            return await sendMessage(message, '<b>This token has already been used!</b>\n\nPlease get a new one.')
        buttons.ibutton('Activate token', f'pass {input_token}', 'header')
        reply_markup = buttons.build_menu(2)
        msg = 'Your token has been successfully generated!\n\n'
        msg += f'It will be valid for {format_validity_time(int(config_dict["TOKEN_TIMEOUT"]))}'
        return await sendMessage(message, msg, reply_markup)
    elif await CustomFilters.authorized(client, message):
        start_string = BotTheme('ST_MSG', help_command=f"/{BotCommands.HelpCommand}")
        await sendMessage(message, start_string, photo='IMAGES')
    elif config_dict['BOT_PM']:
        await sendMessage(message, BotTheme('ST_BOTPM'), photo='IMAGES')
    else:
        await sendMessage(message, BotTheme('ST_UNAUTH'), photo='IMAGES')
    await DbManger().update_pm_users(message.from_user.id)

async def token_callback(_, query):
    user_id = query.from_user.id
    input_token = query.data.split()[1]
    data = user_data.get(user_id, {})
    if 'token' not in data or data['token'] != input_token:
        return await query.answer('Already used, collect new one', show_alert=True)
    update_user_ldata(user_id, 'token', str(uuid4()))
    update_user_ldata(user_id, 'time', time())
    await query.answer('Token activated!', show_alert=True)
    kb = query.message.reply_markup.inline_keyboard[1:]
    kb.insert(0, [InlineKeyboardButton('Activated', callback_data='pass activated')])
    await query.edit_message_reply_markup(InlineKeyboardMarkup(kb))
    
async def restart(client, message):
    restart_message = await sendMessage(message, BotTheme('RESTARTING'))
    if scheduler.running:
        scheduler.shutdown(wait=False)
    for interval in [QbInterval, Interval]:
        if interval:
            interval[0].cancel()
    await sync_to_async(clean_all)
    proc1 = await create_subprocess_exec('pkill', '-9', '-f', '-e', 'gunicorn|buffet|openstack|render|zcl')
    proc2 = await create_subprocess_exec('python3', 'update.py')
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")


async def ping(_, message):
    start_time = int(round(time() * 1000))
    reply = await sendMessage(message, BotTheme('PING'))
    end_time = int(round(time() * 1000))
    await editMessage(reply, BotTheme('PING_VALUE', value=(end_time - start_time)))


@new_task
async def wzmlxcb(_, query):
    message = query.message
    user_id = query.from_user.id
    data = query.data.split()
    if user_id != int(data[1]):
        return await query.answer(text="This message not your's!", show_alert=True)
    elif data[2] == "logdisplay":
        await query.answer()
        async with aiopen('log.txt', 'r') as f:
            logFileLines = (await f.read()).splitlines()
        def parseline(line):
            try:
                return "[" + line.split('] [', 1)[1]
            except IndexError:
                return line
        ind, Loglines = 1, ''
        try:
            while len(Loglines) <= 3500:
                Loglines = parseline(logFileLines[-ind]) + '\n' + Loglines
                if ind == len(logFileLines): 
                    break
                ind += 1
            startLine = f"<b>Showing Last {ind} Lines from log.txt:</b> \n\n----------<b>START LOG</b>----------\n\n"
            endLine = "\n----------<b>END LOG</b>----------"
            btn = ButtonMaker()
            btn.ibutton('Close', f'wzmlx {user_id} close')
            reply_message = await sendMessage(message, startLine + escape(Loglines) + endLine, btn.build_menu(1))
            await query.edit_message_reply_markup(None)
            await deleteMessage(message)
            await one_minute_del(reply_message)
        except Exception as err:
            LOGGER.error(f"TG Log Display : {str(err)}")
    elif data[2] == "botpm":
        await query.answer(url=f"https://t.me/{bot_name}?start=wzmlx")
    else:
        await query.answer()
        await message.delete()
    
@new_task
async def log(_, message):
    buttons = ButtonMaker()
    buttons.ibutton('Log Display', f'wzmlx {message.from_user.id} logdisplay')
    reply_message = await sendFile(message, 'log.txt', buttons=buttons.build_menu(1))
    await deleteMessage(message)
    await one_minute_del(reply_message)

async def search_images():
    if not config_dict['IMG_SEARCH']:
        return
    try:
        query_list = config_dict['IMG_SEARCH']
        total_pages = config_dict['IMG_PAGE']
        base_url = "https://www.wallpaperflare.com/search"

        for query in query_list:
            query = query.strip().replace(" ", "+")
            for page in range(1, total_pages + 1):
                url = f"{base_url}?wallpaper={query}&width=1280&height=720&page={page}"
                r = rget(url)
                soup = BeautifulSoup(r.text, "html.parser")
                images = soup.select('img[data-src^="https://c4.wallpaperflare.com/wallpaper"]')
                for img in images:
                    img_url = img['data-src']
                    if img_url not in config_dict['IMAGES']:
                        config_dict['IMAGES'].append(img_url)
            if DATABASE_URL:
                await DbManger().update_config({'IMAGES': config_dict['IMAGES']})
    except Exception as e:
        LOGGER.error(f"An error occurred: {e}")


help_string = f'''
NOTE: Try each command without any arguments to see more details.
/{BotCommands.MirrorCommand[0]} or /{BotCommands.MirrorCommand[1]}: Starts mirroring to Google Drive.
/{BotCommands.QbMirrorCommand[0]} or /{BotCommands.QbMirrorCommand[1]}: Starts mirroring to Google Drive using qBittorrent.
/{BotCommands.YtdlCommand[0]} or /{BotCommands.YtdlCommand[1]}: Mirrors links supported by yt-dlp.
/{BotCommands.LeechCommand[0]} or /{BotCommands.LeechCommand[1]}: Starts leeching to Telegram.
/{BotCommands.QbLeechCommand[0]} or /{BotCommands.QbLeechCommand[1]}: Starts leeching using qBittorrent.
/{BotCommands.YtdlLeechCommand[0]} or /{BotCommands.YtdlLeechCommand[1]}: Leeches links supported by yt-dlp.
/{BotCommands.CloneCommand} [drive_url]: Copies files/folders to Google Drive.
/{BotCommands.CountCommand} [drive_url]: Counts files/folders in Google Drive.
/{BotCommands.DeleteCommand} [drive_url]: Deletes files/folders from Google Drive (Only Owner & Sudo).
/{BotCommands.UserSetCommand} [query]: User settings.
/{BotCommands.BotSetCommand} [query]: Bot settings.
/{BotCommands.BtSelectCommand}: Select files from torrents by gid or reply.
/{BotCommands.CancelMirror}: Cancels task by gid or reply.
/{BotCommands.CancelAllCommand} [query]: Cancels all [status] tasks.
/{BotCommands.ListCommand} [query]: Searches in Google Drive(s).
/{BotCommands.SearchCommand} [query]: Searches for torrents with API.
/{BotCommands.StatusCommand}: Shows status of all downloads.
/{BotCommands.StatsCommand}: Shows stats of the machine hosting the bot.
/{BotCommands.PingCommand}: Checks how long it takes to ping the bot (Only Owner & Sudo).
/{BotCommands.AuthorizeCommand}: Authorizes a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UnAuthorizeCommand}: Unauthorizes a chat or a user to use the bot (Only Owner & Sudo).
/{BotCommands.UsersCommand}: Shows user settings (Only Owner & Sudo).
/{BotCommands.AddSudoCommand}: Adds sudo user (Only Owner).
/{BotCommands.RmSudoCommand}: Removes sudo users (Only Owner).
/{BotCommands.RestartCommand}: Restarts and updates the bot (Only Owner & Sudo).
/{BotCommands.LogCommand}: Gets a log file of the bot. Handy for getting crash reports (Only Owner & Sudo).
/{BotCommands.ShellCommand}: Runs shell commands (Only Owner).
/{BotCommands.EvalCommand}: Runs Python code line or lines (Only Owner).
/{BotCommands.ExecCommand}: Runs commands in Exec (Only Owner).
/{BotCommands.ClearLocalsCommand}: Clears {BotCommands.EvalCommand} or {BotCommands.ExecCommand} locals (Only Owner).
/{BotCommands.RssCommand}: RSS Menu.
'''

@new_task
async def bot_help(client, message):
    reply_message = await sendMessage(message, help_string)
    await deleteMessage(message)
    await one_minute_del(reply_message)


async def restart_notification():
    now=datetime.now(timezone('Asia/Dhaka'))
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incompelete_task_message(cid, msg):
        try:
            if msg.startswith(BotTheme('RESTART_SUCCESS')):
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=msg)
                await aioremove(".restartmsg")
            else:
                await bot.send_message(chat_id=cid, text=msg, disable_web_page_preview=True,
                                       disable_notification=True)
        except Exception as e:
            LOGGER.error(e)

    if INCOMPLETE_TASK_NOTIFIER and DATABASE_URL:
        if notifier_dict := await DbManger().get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                msg = BotTheme('RESTART_SUCCESS', time=now.strftime('%I:%M:%S %p'), date=now.strftime('%d/%m/%y'))if cid == chat_id else BotTheme('RESTARTED')
                for tag, links in data.items():
                    msg += f"\n\n{tag}: "
                    for index, link in enumerate(links, start=1):
                        msg += f" <a href='{link}'>{index}</a> |"
                        if len(msg.encode()) > 4000:
                            await send_incompelete_task_message(cid, msg)
                            msg = ''
                if msg:
                    await send_incompelete_task_message(cid, msg)

    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=BotTheme('RESTART_SUCCESS', time=now.strftime('%I:%M:%S %p'), date=now.strftime('%d/%m/%y')))
        except:
            pass
        await aioremove(".restartmsg")
        

async def main():
    await gather(start_cleanup(), torrent_search.initiate_search_tools(), restart_notification(), search_images(), set_commands(bot))
    await sync_to_async(start_aria2_listener, wait=False)
    
    bot.add_handler(MessageHandler(
        start, filters=command(BotCommands.StartCommand) & private))
    bot.add_handler(CallbackQueryHandler(
        token_callback, filters=regex(r'^pass')))
    bot.add_handler(MessageHandler(log, filters=command(
        BotCommands.LogCommand) & CustomFilters.sudo))
    bot.add_handler(MessageHandler(restart, filters=command(
        BotCommands.RestartCommand) & CustomFilters.sudo))
    bot.add_handler(MessageHandler(ping, filters=command(
        BotCommands.PingCommand) & CustomFilters.authorized))
    bot.add_handler(MessageHandler(bot_help, filters=command(
        BotCommands.HelpCommand) & CustomFilters.authorized))
    bot.add_handler(MessageHandler(stats, filters=command(
        BotCommands.StatsCommand) & CustomFilters.authorized))
    bot.add_handler(CallbackQueryHandler(wzmlxcb, filters=regex(r'^wzmlx')))
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)

bot.loop.run_until_complete(main())
bot.loop.run_forever()
