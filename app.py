from instagrapi import Client
import time, os, re, requests, json
from datetime import datetime
from colorama import init, Fore, Style
import telebot
from telebot.types import ReplyKeyboardMarkup
import threading
from dotenv import load_dotenv
import glob
import shutil

load_dotenv()
# Inicializa colorama
init(autoreset=True)

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

    def clear_all_cache(self):
        """Limpa TODO o cache quando desloga"""
        try:
            print(f"{Fore.YELLOW}🧹 Limpando todo o cache...{Style.RESET_ALL}")
            
            # 1. Para todos os monitors ativos
            for thread_id in list(self.active_chats.keys()):
                self.stop_monitoring(thread_id)
            
            # 2. Limpa arquivos de sessão
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
                print(f"{Fore.GREEN}✅ Sessão removida{Style.RESET_ALL}")
            
            # 3. Limpa arquivos temporários do instagrapi
            cache_files = [
                "session.json",
                "token.json",
                "settings.json",
                "cookies.json"
            ]
            
            for file in cache_files:
                if os.path.exists(file):
                    os.remove(file)
                    print(f"{Fore.GREEN}✅ {file} removido{Style.RESET_ALL}")
            
            # 4. Limpa possíveis diretórios de cache
            cache_dirs = [
                "__pycache__",
                "*.pyc",
                "*.log",
                "temp",
                "cache"
            ]
            
            for pattern in cache_dirs:
                if os.path.exists(pattern):
                    if os.path.isdir(pattern):
                        shutil.rmtree(pattern)
                    else:
                        for file in glob.glob(pattern):
                            os.remove(file)
            
            # 5. Reseta todas as variáveis
            self.username = None
            self.password = None
            self.access_token = None
            self.redeemed_codes = set()
            self.active_chats = {}
            self.chats_list = []
            self.is_logged_in = False
            
            # 6. Limpa token se existir
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
            
            print(f"{Fore.GREEN}✅ Todo o cache foi limpo!{Style.RESET_ALL}")
            
        except Exception as e:
            print(f"{Fore.RED}❌ Erro ao limpar cache: {e}{Style.RESET_ALL}")

    def setup_client_protection(self):
        self.client.delay_range = [0.1, 0.3]  # MUITO MAIS RÁPIDO
        self.client.request_timeout = 1  # Reduzido timeout
        self.client.set_user_agent("Instagram 269.0.0.18.75 Android (26/8.0.0; 480dpi; 1080x1920; OnePlus; ONEPLUS A6013; OnePlus; qcom; en_US; 314665256)")
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
            # Limpa cache residual antes do login
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
            
            self.username = username
            self.password = password
            
            self.setup_client_protection()
            
            if os.path.exists(self.session_file):
                print(f"{Fore.YELLOW}📁 Carregando sessão...{Style.RESET_ALL}")
                try:
                    self.client.load_settings(self.session_file)
                    user_id = self.client.user_id
                    print(f"{Fore.GREEN}✅ Sessão carregada! User ID: {user_id}{Style.RESET_ALL}")
                    self.is_logged_in = True
                    return True, f"✅ Login com sessão!\n👤 User ID: {user_id}"
                except Exception as e:
                    print(f"{Fore.YELLOW}⚠️ Sessão inválida...{Style.RESET_ALL}")
                    if os.path.exists(self.session_file):
                        os.remove(self.session_file)
            
            print(f"{Fore.YELLOW}🔑 Login rápido...{Style.RESET_ALL}")
            self.client.login(username, password)
            
            self.client.dump_settings(self.session_file)
            user_id = self.client.user_id
            print(f"{Fore.GREEN}✅ Login rápido concluído!{Style.RESET_ALL}")
            self.is_logged_in = True
            return True, f"✅ Login rápido!\n👤 User ID: {user_id}"
                
        except Exception as e:
            print(f"{Fore.RED}❌ Erro login: {e}{Style.RESET_ALL}")
            try:
                print(f"{Fore.YELLOW}🔄 Tentativa rápida...{Style.RESET_ALL}")
                self.client.login(username, password, relogin=True)
                self.client.dump_settings(self.session_file)
                user_id = self.client.user_id
                print(f"{Fore.GREEN}✅ Login rápido alternativo!{Style.RESET_ALL}")
                self.is_logged_in = True
                return True, f"✅ Login rápido alternativo!\n👤 User ID: {user_id}"
            except Exception as e2:
                print(f"{Fore.RED}❌ Falha rápida: {e2}{Style.RESET_ALL}")
                self.is_logged_in = False
                return False, f"❌ Erro: {e2}"

    # ... (o resto dos métodos permanecem iguais)

    def list_chats(self):
        if not self.is_logged_in:
            return []
        
        try:
            print(f"{Fore.CYAN}🚀 Busca RÁPIDA de chats...{Style.RESET_ALL}")
            
            # BUSCA TODOS OS CHATS SEM FILTRO - MAIS RÁPIDO
            threads = []
            
            try:
                print(f"{Fore.YELLOW}⚡ Buscando TODOS os chats...{Style.RESET_ALL}")
                threads = self.client.direct_threads(amount=100)  # MAIS CHATS
                print(f"{Fore.GREEN}✅ {len(threads)} chats encontrados{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}❌ Erro busca rápida: {e}{Style.RESET_ALL}")
                try:
                    threads = self.client.direct_threads()
                    print(f"{Fore.GREEN}✅ {len(threads)} chats método 2{Style.RESET_ALL}")
                except Exception as e2:
                    print(f"{Fore.RED}❌ Falha método 2: {e2}{Style.RESET_ALL}")
                    return []
            
            # MOSTRA TODOS OS CHATS, NÃO FILTRA - PARA VER TUDO
            all_chats = []
            for thread in threads:
                all_chats.append(thread)
            
            print(f"{Fore.CYAN}📊 Total: {len(all_chats)} chats{Style.RESET_ALL}")
            
            # DEBUG: Mostra info de cada chat
            for i, chat in enumerate(all_chats[:25]):  # Mostra apenas os 10 primeiros
                users = chat.users if hasattr(chat, 'users') else []
                title = getattr(chat, 'thread_title', 'Sem título')
                print(f"{Fore.MAGENTA}Chat {i+1}: {title} - Users: {len(users)}{Style.RESET_ALL}")
                for user in users[:3]:  # Mostra até 3 usuários
                    print(f"  👤 {user.username}")
            
            self.chats_list = all_chats
            return all_chats
            
        except Exception as e:
            print(f"{Fore.RED}❌ Erro geral: {e}{Style.RESET_ALL}")
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
                timeout=5  # MAIS RÁPIDO
            )
            return response.text
        except:
            return None

    def redeem_code(self, code, chat_name):
        if code in self.redeemed_codes:
            return f"⚠️ {code} já resgatado"

        url = "https://prod-api.reward.ff.garena.com/redemption/api/game/ff/redeem/"
        headers = {"access-token": self.access_token, "content-type": "application/json", "user-agent": "Mozilla/5.0"}
        payload = {"serialno": code}

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=5)  # MAIS RÁPIDO
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
        except Exception as e:
            return f"⚡ Erro: {code}"

    def monitor_chat(self, thread_id, chat_name):
        try:
            print(f"{Fore.GREEN}🚀 Monitoramento ULTRA-RÁPIDO: {chat_name}{Style.RESET_ALL}")
            last_check = time.time()
            
            while thread_id in self.active_chats and self.active_chats[thread_id]["monitoring"]:
                try:
                    current_time = time.time()
                    # Verifica a cada 0.5 segundos! (ULTRA RÁPIDO)
                    if current_time - last_check >= 0.5:
                        thread = self.client.direct_thread(thread_id)
                        if thread.messages:
                            newest = thread.messages[0]
                            last_message_id = self.active_chats[thread_id]["last_message_id"]

                            if newest.id != last_message_id:
                                print(f"{Fore.CYAN}⚡ NOVA MENSAGEM em {chat_name}{Style.RESET_ALL}")
                                # Processa apenas a mensagem mais recente para ser mais rápido
                                latest_msg = thread.messages[0]
                                if last_message_id is None or latest_msg.id > last_message_id:
                                    sender = self.get_sender_name(latest_msg)
                                    content = getattr(latest_msg, "text", "<mídia>")
                                    text = f"[{datetime.now().strftime('%H:%M:%S')}] {sender}: {content}"
                                    self.bot.send_message(self.allowed_user_id, f"<b>{chat_name}</b>\n{text}", parse_mode="HTML")

                                    if getattr(latest_msg, "text", None):
                                        codes = re.findall(r"\b[A-Z0-9]{12}\b", latest_msg.text)
                                        for code in codes:
                                            print(f"{Fore.YELLOW}🎯 CÓDIGO RÁPIDO: {code}{Style.RESET_ALL}")
                                            result = self.redeem_code(code, chat_name)
                                            self.bot.send_message(self.allowed_user_id, f"🎯 Código: <code>{code}</code>\n{result}", parse_mode="HTML")

                                self.active_chats[thread_id]["last_message_id"] = newest.id
                        
                        last_check = current_time
                    
                    time.sleep(0.1)  # CHECK MUITO RÁPIDO
                    
                except Exception as e:
                    print(f"{Fore.RED}❌ Erro loop rápido: {e}{Style.RESET_ALL}")
                    time.sleep(0.5)
        except Exception as e:
            error_msg = f"❌ Erro monitor: {chat_name}: {e}"
            print(f"{Fore.RED}{error_msg}{Style.RESET_ALL}")
            self.bot.send_message(self.allowed_user_id, error_msg)

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

        self.active_chats[thread_id] = {
            "name": chat_name,
            "monitoring": True,
            "last_message_id": last_message_id
        }

        t = threading.Thread(target=self.monitor_chat, args=(thread_id, chat_name), daemon=True)
        t.start()
        return True, f"🚀 Monitor ULTRA-RÁPIDO: {chat_name}"

    def stop_monitoring(self, thread_id):
        if thread_id in self.active_chats:
            self.active_chats[thread_id]["monitoring"] = False
            del self.active_chats[thread_id]
            return True, "Parado"
        return False, "Não encontrado"

# ---------- BOT TELEGRAM RÁPIDO ----------

def setup_bot(token, allowed_user_id):
    bot = telebot.TeleBot(token)
    monitor = InstagramChatMonitor(bot, allowed_user_id)

    def auth(message):
        return message.from_user.id == allowed_user_id

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
        bot.send_message(message.chat.id, "🤖 Bot ULTRA-RÁPIDO ativo!", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🔐 Login Rápido")
    def iniciar_login(message):
        msg = bot.send_message(message.chat.id, "🔐 <b>Login RÁPIDO Instagram</b>\n\nUsername:", parse_mode="HTML")
        bot.register_next_step_handler(msg, processar_username)

    def processar_username(message):
        username = message.text.strip()
        msg = bot.send_message(message.chat.id, f"👤: <code>{username}</code>\n\nSenha:", parse_mode="HTML")
        bot.register_next_step_handler(msg, processar_senha, username)

    def processar_senha(message, username):
        password = message.text.strip()
        bot.send_message(message.chat.id, f"⚡ Login rápido: <code>{username}</code>...", parse_mode="HTML")
        
        def fazer_login():
            success, result = monitor.login(username, password)
            bot.send_message(message.chat.id, result, parse_mode="HTML", reply_markup=main_menu())
        
        threading.Thread(target=fazer_login).start()

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🚪 Sair")
    def logout(message):
        # CHAMA A LIMPEZA DE CACHE ANTES DE SAIR
        monitor.clear_all_cache()
        bot.send_message(message.chat.id, "✅ Logout e cache limpo! Nova sessão ficará limpa.", reply_markup=main_menu())

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
            for i, th in enumerate(threads[:25], 1):  # Mostra apenas 15 para não ficar grande
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
            numbers = [str(i) for i in range(1, min(len(threads), 25) + 1)]  # Máximo 10
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
                    chat_name = ", ".join(u.username for u in selected_chat.users) if selected_chat.users else "Chat"
                
                ok, res = monitor.start_monitoring(selected_chat.id, chat_name)
                bot.send_message(message.chat.id, res, reply_markup=main_menu())
            else:
                bot.send_message(message.chat.id, "❌ Número inválido.", reply_markup=main_menu())
        except ValueError:
            bot.send_message(message.chat.id, "❌ Número inválido.", reply_markup=main_menu())

    @bot.message_handler(func=lambda m: auth(m) and m.text == "⏹️ Parar Monitor")
    def parar(message):
        if not monitor.active_chats:
            bot.send_message(message.chat.id, "Nenhum chat ativo.")
            return
        for tid in list(monitor.active_chats.keys()):
            monitor.stop_monitoring(tid)
        bot.send_message(message.chat.id, "✅ Todos parados.")

    @bot.message_handler(func=lambda m: auth(m) and m.text == "📊 Status")
    def status(message):
        if monitor.is_logged_in:
            txt = f"<b>📊 Status ULTRA-RÁPIDO:</b>\n\n✅ Logado: {monitor.username}\n📱 Chats ativos: {len(monitor.active_chats)}\n🎯 Códigos: {len(monitor.redeemed_codes)}\n⚡ Delay: 0.5s"
        else:
            txt = "<b>📊 Status:</b>\n\n❌ Não logado\n📱 Chats ativos: 0\n🎯 Códigos: 0"
        bot.send_message(message.chat.id, txt, parse_mode="HTML")

    @bot.message_handler(func=lambda m: auth(m) and m.text == "🔑 Token")
    def definir_token(message):
        msg = bot.send_message(message.chat.id, "Token:")
        bot.register_next_step_handler(msg, salvar_token)

    def salvar_token(message):
        token = message.text.strip()
        monitor.access_token = token
        monitor.save_access_token(token)
        bot.send_message(message.chat.id, "✅ Token!", reply_markup=main_menu())

    return bot, monitor

# ---------- EXECUÇÃO RÁPIDA ----------

def main():
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID"))

    print(f"{Fore.CYAN}🚀 Bot ULTRA-RÁPIDO iniciando...{Style.RESET_ALL}")
    
    bot, monitor = setup_bot(TELEGRAM_TOKEN, ALLOWED_USER_ID)
    
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"{Fore.RED}❌ Erro: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
