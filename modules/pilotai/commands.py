import asyncio
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import discord
from discord.ext import commands
from openai import OpenAI


class PilotAI(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        # OpenAI client reads OPENAI_API_KEY from env
        self.client = OpenAI()

        # Choose your model centrally (env override supported)
        self.model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        # ================= Conversation memory with TTL =================
        self.system_prompt = (
            "You are guildPilot, a helpful integrated Discord chat assistant. "
            "Be concise, clear, and friendly. Use markdown when helpful."
        )

        self.max_turns = 12  # keep last ~12 user/assistant turns
        self.convo_ttl = timedelta(hours=2)  # flush after 2 hours of inactivity
        self.cleanup_period = 300  # seconds (5 min)

        # convos[root_id] = {"history": [...], "last_active": datetime, "channel_id": int}
        self.convos: dict[int, dict[str, Any]] = {}
        # map any bot message id in a convo back to its root id
        self.msg_to_root: dict[int, int] = {}

        self._cleanup_task: asyncio.Task | None = None

    def utcnow(self) -> datetime:
        return datetime.now(UTC)

    def trim_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        """Keep system + last N user/assistant turns."""
        sys = [m for m in history if m["role"] == "system"][:1]
        rest = [m for m in history if m["role"] != "system"][-2 * self.max_turns :]
        return sys + rest

    def is_expired(self, root_id: int) -> bool:
        meta = self.convos.get(root_id)
        if not meta:
            return True
        return self.utcnow() - meta["last_active"] > self.convo_ttl

    async def send_long_message(self, channel: discord.abc.Messageable, content: str):
        # Discord hard limit ~2000 chars
        for i in range(0, len(content), 2000):
            await channel.send(content[i : i + 2000])

    def llm_reply(self, history: list[dict[str, str]]) -> str:
        """
        history: list of {"role": "system"|"user"|"assistant", "content": "..."}
        returns: string reply
        """
        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=self.trim_history(history),
            temperature=0.9,
            max_tokens=1024,
        )
        return (
            resp.choices[0].message.content
            if resp.choices
            else "No response from OpenAI."
        )

    async def cleanup_conversations_task(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                now = self.utcnow()
                to_delete: list[int] = []
                for root_id, meta in list(self.convos.items()):
                    if now - meta["last_active"] > self.convo_ttl:
                        to_delete.append(root_id)

                for root_id in to_delete:
                    del self.convos[root_id]
                    # remove any msg_to_root entries that map to this root
                    for mid in [k for k, v in list(self.msg_to_root.items()) if v == root_id]:
                        del self.msg_to_root[mid]
            except Exception as e:
                print(f"[pilotai.cleanup] error: {e!r}")

            await asyncio.sleep(self.cleanup_period)

    # py-cord calls this when the cog is added (2.6+)
    def cog_load(self) -> None:
        if self._cleanup_task is None:
            self._cleanup_task = self.bot.loop.create_task(self.cleanup_conversations_task())

    # ================== Slash command: start a new conversation ==================
    @commands.slash_command(
        name="ask-the-pilot",
        description="Talk to the pilot, he can probably help",
    )
    async def ask_the_pilot(self, ctx: discord.ApplicationContext, message: str):
        # Start "thinking..."
        try:
            await ctx.defer(ephemeral=True)
        except Exception:
            pass

        try:
            history = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message},
            ]

            reply = self.llm_reply(history)

            user_name = ctx.author.display_name
            server_location = ctx.guild.name if ctx.guild else "DM"
            channel_location = ctx.channel.name if hasattr(ctx.channel, "name") else "DM"

            # End thinking — only user sees this
            try:
                await ctx.respond("✈️ Response posted below.", ephemeral=True)
            except Exception:
                pass

            # Post the real response publicly (reliable Message object)
            if len(reply) > 2000:
                sent_msg = await ctx.channel.send(reply[:2000])
                await self.send_long_message(ctx.channel, reply[2000:])
            else:
                sent_msg = await ctx.channel.send(reply)

            root_id = sent_msg.id

            history.append({"role": "assistant", "content": reply})
            self.convos[root_id] = {
                "history": self.trim_history(history),
                "last_active": self.utcnow(),
                "channel_id": ctx.channel.id,
            }
            self.msg_to_root[root_id] = root_id

            print(
                f"[pilotai] user: {user_name}\n"
                f"[pilotai] reply: {reply[:120]}...\n"
                f"[pilotai] Server: {server_location}\n"
                f"[pilotai] Channel: {channel_location}"
            )

        except Exception as e:
            print(f"[pilotai] Error: {e!r}")
            try:
                await ctx.respond("There was an error processing your request.", ephemeral=True)
            except Exception:
                pass

    # ================== Reply-to-continue handler with TTL ==================
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots
        if message.author.bot:
            return

        # If user replies to a bot message, continue that conversation
        if message.reference and (message.reference.resolved or message.reference.message_id):
            try:
                ref = message.reference.resolved
                if not ref:
                    ref = await message.channel.fetch_message(message.reference.message_id)
            except Exception:
                ref = None

            if ref and self.bot.user and ref.author.id == self.bot.user.id:
                root_id = self.msg_to_root.get(ref.id, ref.id)

                if self.is_expired(root_id):
                    history = [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "assistant", "content": ref.content},
                        {"role": "user", "content": message.content},
                    ]
                else:
                    meta = self.convos[root_id]
                    history = meta["history"] + [{"role": "user", "content": message.content}]

                try:
                    reply = self.llm_reply(history)
                except Exception as e:
                    print(f"[pilotai] OpenAI error: {e!r}")
                    await message.reply("Sorry, I hit an error talking to OpenAI.")
                    return

                if len(reply) > 2000:
                    sent = await message.reply(reply[:2000])
                    await self.send_long_message(message.channel, reply[2000:])
                else:
                    sent = await message.reply(reply)

                history.append({"role": "assistant", "content": reply})
                self.convos[root_id] = {
                    "history": self.trim_history(history),
                    "last_active": self.utcnow(),
                    "channel_id": message.channel.id,
                }

                self.msg_to_root[sent.id] = root_id
                self.msg_to_root[ref.id] = root_id

                return  # do not fall through

        # Let other commands/cogs work normally
        await self.bot.process_commands(message)


def setup(bot: commands.Bot):
    bot.add_cog(PilotAI(bot))
