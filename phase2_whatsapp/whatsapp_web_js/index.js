/**
 * whatsapp-web.js Node.js server (Option B)
 *
 * - Connects to WhatsApp via QR code scan (one-time)
 * - Listens for incoming messages → forwards to Python via HTTP POST
 * - Exposes HTTP API for Python to call:  POST /send  { phone, message }
 * - Saves session for auto-reconnect
 */

const { Client, LocalAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode-terminal");
const express = require("express");
const bodyParser = require("body-parser");

// ── Config ──────────────────────────────────────────────────────
const PORT = process.env.WJS_PORT || 3001;
const PYTHON_WEBHOOK_URL =
  process.env.PYTHON_WEBHOOK_URL || "http://localhost:8000/webhook/incoming";

// ── WhatsApp Client ─────────────────────────────────────────────
const client = new Client({
  authStrategy: new LocalAuth({ dataPath: "./.wwebjs_auth" }),
  puppeteer: {
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
    ],
  },
});

let isReady = false;

client.on("qr", (qr) => {
  console.log("\n📱 Scan this QR code with WhatsApp:\n");
  qrcode.generate(qr, { small: true });
});

client.on("ready", () => {
  isReady = true;
  console.log("✅ WhatsApp client is ready!");
});

client.on("authenticated", () => {
  console.log("🔐 Authenticated successfully. Session saved.");
});

client.on("auth_failure", (msg) => {
  console.error("❌ Authentication failed:", msg);
});

client.on("disconnected", (reason) => {
  isReady = false;
  console.warn("⚠️ Disconnected:", reason);
  console.log("🔄 Attempting to reconnect...");
  client.initialize();
});

// ── Forward incoming messages to Python ─────────────────────────
client.on("message", async (msg) => {
  // Skip group messages, status updates, etc.
  if (msg.isGroupMsg || msg.isStatus) return;

  const payload = {
    phone: msg.from.replace("@c.us", ""),
    message: msg.body,
    message_id: msg.id._serialized,
    timestamp: msg.timestamp,
    name: (await msg.getContact()).pushname || "",
    type: msg.type,
  };

  console.log(`📥 Incoming from ${payload.phone}: ${payload.message.substring(0, 80)}`);

  try {
    const resp = await fetch(PYTHON_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!resp.ok) {
      console.error(`❌ Python webhook responded with ${resp.status}`);
    }
  } catch (err) {
    console.error("❌ Failed to forward message to Python:", err.message);
  }
});

// ── Express API server ──────────────────────────────────────────
const app = express();
app.use(bodyParser.json());

// Health check
app.get("/health", (_req, res) => {
  res.json({ status: isReady ? "ready" : "not_ready" });
});

// Send a message
app.post("/send", async (req, res) => {
  const { phone, message } = req.body;

  if (!phone || !message) {
    return res.status(400).json({ error: "phone and message are required" });
  }

  if (!isReady) {
    return res.status(503).json({ error: "WhatsApp client is not ready" });
  }

  // Format phone for WhatsApp: country code + number @ c.us
  let chatId = phone.replace(/[^\d]/g, "");
  if (!chatId.includes("@")) {
    chatId += "@c.us";
  }

  try {
    const sent = await client.sendMessage(chatId, message);
    console.log(`📤 Sent to ${phone}: ${message.substring(0, 80)}`);
    res.json({ success: true, message_id: sent.id._serialized });
  } catch (err) {
    console.error(`❌ Send failed to ${phone}:`, err.message);
    res.status(500).json({ error: err.message });
  }
});

// ── Start ───────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`🚀 whatsapp-web.js API server listening on port ${PORT}`);
});

client.initialize();
