import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from arbitrage import AzuroArbitrage
from config import Config

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

config = Config()
arb = AzuroArbitrage(config)
is_running = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Azuro Arbitraj Botu*\n\n"
        "Komutlar:\n"
        "/run - Botu başlat\n"
        "/stop - Botu durdur\n"
        "/status - Durum ve bakiye\n"
        "/history - Son bahisler",
        parse_mode='Markdown'
    )

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    if is_running:
        await update.message.reply_text("⚠️ Bot zaten çalışıyor!")
        return
    is_running = True
    await update.message.reply_text("✅ Bot başlatıldı! Marketler taranıyor...")
    asyncio.create_task(run_loop(update, context))

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    is_running = False
    await update.message.reply_text("🛑 Bot durduruldu.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        balance = await arb.get_balance()
        status = "🟢 Çalışıyor" if is_running else "🔴 Durdu"
        await update.message.reply_text(
            f"📊 *Bot Durumu*\n\n"
            f"Durum: {status}\n"
            f"USDC Bakiye: `{balance:.2f}` USDC\n"
            f"Toplam Bahis: `{arb.total_bets}`\n"
            f"Net Kar: `{arb.net_profit:.2f}` USDC",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Hata: {e}")

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not arb.bet_history:
        await update.message.reply_text("Henüz bahis geçmişi yok.")
        return
    msg = "📋 *Son 10 Bahis*\n\n"
    for bet in arb.bet_history[-10:]:
        emoji = "✅" if bet['won'] else "❌" if bet['resolved'] else "⏳"
        msg += f"{emoji} {bet['sport']} | {bet['match']}\n"
        msg += f"   Oran: {bet['odds']:.2f} | Miktar: {bet['amount']} USDC\n\n"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def run_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_running
    while is_running:
        try:
            opportunities = await arb.scan_markets()
            if opportunities:
                for opp in opportunities:
                    if not is_running:
                        break
                    result = await arb.place_bet(opp)
                    if result:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=(
                                f"🎯 *Bahis Oynadı!*\n\n"
                                f"🏆 {opp['sport']}\n"
                                f"⚔️ {opp['match']}\n"
                                f"📈 Oran: `{opp['odds']:.2f}`\n"
                                f"💰 {opp['amount']} USDC\n"
                                f"🎯 İhtimal: `%{opp['win_prob']:.0f}`"
                            ),
                            parse_mode='Markdown'
                        )
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Döngü hatası: {e}")
            await asyncio.sleep(30)

def main():
    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("history", history_command))
    logger.info("Bot başlatıldı...")
    app.run_polling()

if __name__ == "__main__":
    main()
