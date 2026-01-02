"""
Example Poker Bot Template
This bot demonstrates how to connect and interact with the tournament server.
"""

import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any

class PokerBot:
    def __init__(self, server_url: str, username: str):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.player_id: Optional[str] = None
        self.api_key: Optional[str] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False

    async def register(self) -> bool:
        """Register the bot with the tournament server"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.server_url}/bot/register",
                json={"username": self.username}
            ) as resp:
                data = await resp.json()
                
                if data.get("success"):
                    self.player_id = data["player_id"]
                    self.api_key = data["api_key"]
                    print(f"✅ Registered as {self.username}")
                    print(f"   Player ID: {self.player_id}")
                    return True
                else:
                    print(f"❌ Registration failed: {data.get('message')}")
                    return False

    async def connect_websocket(self):
        """Connect to the game WebSocket"""
        if not self.player_id:
            print("❌ Must register before connecting")
            return

        ws_url = self.server_url.replace("http", "ws")
        self.session = aiohttp.ClientSession()
        
        try:
            self.ws = await self.session.ws_connect(
                f"{ws_url}/bot/ws/{self.player_id}"
            )
            print(f"✅ WebSocket connected")
            self.running = True
            
            # Start message handler
            await self._handle_messages()
            
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
        finally:
            if self.session:
                await self.session.close()

    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        async for msg in self.ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._process_message(data)
                except json.JSONDecodeError:
                    print(f"Invalid JSON: {msg.data}")
                    
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"WebSocket error: {self.ws.exception()}")
                break
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                print("WebSocket closed")
                break

    async def _process_message(self, message: Dict[str, Any]):
        """Process a message from the server"""
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "connected":
            print(f"📡 Connected to tournament")
            print(f"   Status: {data.get('tournament_status')}")

        elif msg_type == "game_state":
            await self._handle_game_state(data)

        elif msg_type == "action_result":
            if data.get("success"):
                print(f"✅ Action accepted")
            else:
                print(f"❌ Action rejected: {data.get('message')}")

        elif msg_type == "kicked":
            print(f"🚫 Kicked from tournament: {data.get('reason')}")
            self.running = False

        elif msg_type == "tournament_complete":
            winner = data.get("winner", {})
            print(f"🏆 Tournament complete! Winner: {winner.get('username')}")
            self.running = False

    async def _handle_game_state(self, game_state: Dict[str, Any]):
        """Handle game state update and decide action"""
        current_player = game_state.get("current_player_id")
        
        # Check if it's our turn
        if current_player != self.player_id:
            return

        print(f"\n{'='*50}")
        print(f"🎯 YOUR TURN!")
        print(f"   Round: {game_state.get('betting_round')}")
        print(f"   Pot: {game_state.get('total_pot')}")
        print(f"   Current bet: {game_state.get('current_bet')}")
        
        # Show our cards
        our_cards = game_state.get("your_hole_cards", [])
        if our_cards:
            cards_str = " ".join([f"{c['rank']}{c['suit']}" for c in our_cards])
            print(f"   Your cards: {cards_str}")

        # Show community cards
        community = game_state.get("community_cards", [])
        if community:
            comm_str = " ".join([f"{c['rank']}{c['suit']}" for c in community])
            print(f"   Community: {comm_str}")

        # Get valid actions
        valid_actions = game_state.get("valid_actions", [])
        print(f"   Valid actions: {[a['action_type'] for a in valid_actions]}")

        # Decide and send action
        action = self.decide_action(game_state, valid_actions)
        await self.send_action(action["action_type"], action.get("amount"))

    def decide_action(self, game_state: Dict, valid_actions: list) -> Dict:
        """
        Decide what action to take.
        Override this method to implement your bot's strategy!
        """
        # Default strategy: Call if possible, otherwise check, otherwise fold
        action_types = [a["action_type"] for a in valid_actions]

        if "call" in action_types:
            call_action = next(a for a in valid_actions if a["action_type"] == "call")
            return {"action_type": "call", "amount": call_action["min_amount"]}
        
        elif "check" in action_types:
            return {"action_type": "check"}
        
        else:
            return {"action_type": "fold"}

    async def send_action(self, action_type: str, amount: Optional[int] = None):
        """Send an action to the server"""
        if not self.ws:
            print("❌ Not connected")
            return

        message = {
            "type": "action",
            "data": {
                "action_type": action_type,
                "amount": amount
            }
        }

        await self.ws.send_json(message)
        print(f"📤 Sent action: {action_type}" + (f" ({amount})" if amount else ""))

    async def run(self):
        """Main bot loop"""
        if not await self.register():
            return

        print(f"\n⏳ Waiting for tournament to start...")
        print(f"   Connect to the admin panel to start the tournament")
        
        await self.connect_websocket()


# Run the bot
if __name__ == "__main__":
    import sys
    
    server = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    username = sys.argv[2] if len(sys.argv) > 2 else f"TestBot_{id(object())%1000}"

    bot = PokerBot(server, username)
    asyncio.run(bot.run())