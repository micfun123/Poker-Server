"""
My First Poker Bot
"""

import asyncio
import aiohttp
import json

class MyPokerBot:
    def __init__(self, server_url, bot_name):
        self.server_url = server_url
        self.bot_name = bot_name
        self.player_id = None
        self.api_key = None
    
    async def register(self):
        """Register the bot with the tournament"""
        print(f"Registering bot '{self.bot_name}'...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.server_url}/bot/register",
                json={"username": self.bot_name}
            ) as response:
                data = await response.json()
                
                if data.get("success"):
                    self.player_id = data["player_id"]
                    self.api_key = data["api_key"]
                    print(f"✅ Registration successful!")
                    print(f"   Player ID: {self.player_id}")
                    return True
                else:
                    print(f"❌ Registration failed: {data.get('message')}")
                    return False
    
    async def connect_and_play(self):
        """Connect to game and start playing"""
        ws_url = self.server_url.replace("http", "ws")
        
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(f"{ws_url}/bot/ws/{self.player_id}") as ws:
                print("✅ Connected to game server!")
                print("⏳ Waiting for tournament to start...")
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self.handle_message(ws, json.loads(msg.data))
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print(f"❌ Connection error")
                        break
    
    async def handle_message(self, ws, message):
        """Handle incoming messages from server"""
        msg_type = message.get("type")
        data = message.get("data", {})
        
        if msg_type == "game_state":
            # Check if it's our turn
            if data.get("current_player_id") == self.player_id:
                await self.take_action(ws, data)
        
        elif msg_type == "tournament_complete":
            winner = data.get("winner", {})
            print(f"🏆 Tournament over! Winner: {winner.get('username')}")
    
    async def take_action(self, ws, game_state):
        """Decide and send our action"""
        print("\n" + "="*50)
        print("🎯 YOUR TURN!")
        
        # Show our cards
        our_cards = game_state.get("your_hole_cards", [])
        cards_str = " ".join([f"{c['rank']}{c['suit']}" for c in our_cards])
        print(f"   Your cards: {cards_str}")
        
        # Show game info
        print(f"   Pot: {game_state.get('total_pot')}")
        print(f"   To call: {game_state.get('current_bet')}")
        
        # Get valid actions
        valid_actions = game_state.get("valid_actions", [])
        action_types = [a["action_type"] for a in valid_actions]
        print(f"   Options: {action_types}")
        
        # DECIDE WHAT TO DO - This is where your strategy goes!
        action = self.decide_action(game_state, valid_actions)
        
        # Send the action
        await ws.send_json({
            "type": "action",
            "data": action
        })
        print(f"   ➡️ Action: {action['action_type']}")
    
    def decide_action(self, game_state, valid_actions):
        """
        YOUR STRATEGY GOES HERE!
        
        This simple strategy:
        - Calls if possible
        - Checks if can't call
        - Folds as last resort
        """
        action_types = [a["action_type"] for a in valid_actions]
        
        # Try to call
        if "call" in action_types:
            return {"action_type": "call", "amount": None}
        
        # Try to check
        if "check" in action_types:
            return {"action_type": "check", "amount": None}
        
        # Fold if nothing else
        return {"action_type": "fold", "amount": None}
    
    async def run(self):
        """Main function to run the bot"""
        if await self.register():
            await self.connect_and_play()


# RUN THE BOT
if __name__ == "__main__":
    # CHANGE THESE VALUES:
    SERVER = "http://localhost:8000"  # Get from tournament admin
    BOT_NAME = "MyFirstBot"           # Choose a unique name
    
    bot = MyPokerBot(SERVER, BOT_NAME)
    asyncio.run(bot.run())