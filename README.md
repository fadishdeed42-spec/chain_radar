# Chain Radar

Crypto news scanner for **Chain Secrets**. Every 15 minutes (GitHub Actions) it reads free sources —
CoinDesk, Cointelegraph, Decrypt, The Block, Bitcoin Magazine, CryptoSlate, Blockworks, Google News,
Reddit r/CryptoCurrency, CoinGecko prices and DefiLlama hacks — groups duplicate stories, scores how viral
each one is likely to be (0–100) and sends a Telegram alert with a branded chart and a draft X post.

- 🚨 score ≥ 65, hacks ≥ $1M, big price moves → instant alert
- 📌 score 50–64 → "worth a look" list
- Secrets: `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, optional `GEMINI_API_KEY` (better drafts)
- Run manually: Actions → radar → Run workflow
