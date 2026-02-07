# University Poker Bot Tournament

A complete backend system for hosting poker bot competitions where students write their own bots to compete.

## Features

- **Full Texas Hold'em Implementation**: Complete game logic with proper betting rounds
- **Rule Enforcement**: Server-side validation of all player actions
- **Real-time Updates**: WebSocket-based communication for instant game updates
- **Admin Panel**: Web interface to manage tournaments
- **Live Viewer**: Watch games unfold in real-time
- **Bot API**: Simple API for bots to register and play
- **Tournament Management**: Automatic table balancing, blind increases, eliminations

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## API Reference

### Root Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root page with links to all interfaces |
| `/health` | GET | Health check endpoint |
| `/docs` | GET | Swagger UI interactive documentation |
| `/redoc` | GET | ReDoc API documentation |
| `/static/viewer.html` | GET | Tournament viewer interface |
| `/static/admin.html` | GET | Admin panel interface |

---

## Bot API Endpoints

All bot endpoints are prefixed with `/bot`.

### REST Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/bot/register` | POST | None | Register a new bot for the tournament |
| `/bot/action` | POST | API Key | Submit a poker action |
| `/bot/state` | GET | API Key | Get current game state |
| `/bot/valid-actions` | GET | API Key | Get list of valid actions for current turn |

#### POST `/bot/register`

Register a new bot for the tournament.

**Request Body:**
```json
{
  "username": "MyBot",
  "team_name": "Team Alpha"  // optional
}
```

**Response:**
```json
{
  "success": true,
  "player_id": "player_1_abc123",
  "api_key": "your-secret-api-key",
  "message": "Successfully registered as 'MyBot'",
  "websocket_url": "/ws/player/player_1_abc123"
}
```

#### POST `/bot/action`

Submit a poker action. Requires `X-API-Key` header.

**Headers:**
```
X-API-Key: your-secret-api-key
```

**Request Body:**
```json
{
  "action_type": "call",
  "amount": null
}
```

**Valid Action Types:**
- `fold` - Fold your hand
- `check` - Check (when no bet to call)
- `call` - Call the current bet
- `bet` - Place a bet (requires `amount`)
- `raise` - Raise the current bet (requires `amount`)
- `all_in` - Go all-in with all your chips

**Response:**
```json
{
  "success": true,
  "message": "Action accepted: call",
  "action_accepted": {
    "type": "call",
    "amount": 20
  },
  "game_state": { ... }
}
```

#### GET `/bot/state`

Get current game state for your bot. Requires `X-API-Key` header.

#### GET `/bot/valid-actions`

Get list of valid actions for the current game state. Requires `X-API-Key` header.

---

### Bot WebSocket

**Endpoint:** `ws://<host>/bot/ws/{player_id}`

Connect to receive real-time game updates and send actions.

#### Messages FROM Server (Bot Receives)

| Type | Description |
|------|-------------|
| `connected` | Initial connection confirmation with game state |
| `game_state` | Updated game state after any change |
| `action_result` | Result of a submitted action |
| `table_change` | Notification when moved to a new table |
| `elimination` | Notification of player eliminations |
| `tournament_complete` | Tournament has ended with final standings |
| `kicked` | You have been kicked from the tournament |
| `admin_message` | Broadcast message from admin |
| `pong` | Response to ping |
| `error` | Error message |

##### `connected` Message
```json
{
  "type": "connected",
  "data": {
    "player_id": "player_1_abc123",
    "tournament_status": "running",
    "game_state": { ... }
  }
}
```

##### `game_state` Message
```json
{
  "type": "game_state",
  "data": {
    "game_id": "...",
    "table_id": "table_1",
    "hand_number": 5,
    "phase": "betting",
    "betting_round": "flop",
    "community_cards": ["Ah", "Kd", "7s"],
    "your_hole_cards": ["As", "Ks"],
    "current_player_id": "player_1_abc123",
    "pot": 150,
    "current_bet": 40,
    "your_chips": 980,
    "valid_actions": ["fold", "call", "raise"],
    "players": { ... }
  },
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

##### `action_result` Message
```json
{
  "type": "action_result",
  "data": {
    "success": true,
    "message": "Action accepted: call"
  }
}
```

##### `table_change` Message
```json
{
  "type": "table_change",
  "data": {
    "new_table_id": "table_2",
    "message": "You have been moved to a new table"
  }
}
```

##### `tournament_complete` Message
```json
{
  "type": "tournament_complete",
  "data": {
    "winner": {
      "player_id": "player_1_abc123",
      "username": "WinningBot",
      "chips": 10000
    },
    "standings": [...],
    "total_hands": 150,
    "duration_seconds": 3600
  }
}
```

##### `kicked` Message
```json
{
  "type": "kicked",
  "data": {
    "reason": "Kicked by admin"
  }
}
```

##### `error` Message
```json
{
  "type": "error",
  "data": {
    "message": "Invalid JSON"
  }
}
```

#### Messages TO Server (Bot Sends)

| Type | Description |
|------|-------------|
| `action` | Submit a poker action |
| `ping` | Keep-alive ping |

##### `action` Message
```json
{
  "type": "action",
  "data": {
    "action_type": "call",
    "amount": null
  }
}
```

##### `ping` Message
```json
{
  "type": "ping"
}
```

---

## Viewer API Endpoints

All viewer endpoints are prefixed with `/viewer`. No authentication required.

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/viewer/status` | GET | Get public tournament status |
| `/viewer/tables` | GET | Get public table states (hole cards hidden) |
| `/viewer/leaderboard` | GET | Get current chip leaderboard |

### Viewer WebSocket

**Endpoint:** `ws://<host>/viewer/ws`

Connect to receive real-time tournament updates.

#### Messages FROM Server (Viewer Receives)

| Type | Description |
|------|-------------|
| `connected` | Initial connection with tournament status and tables |
| `game_state` | Updated public game state (hole cards hidden) |
| `elimination` | Player elimination notification |
| `tournament_complete` | Tournament has ended with final standings |
| `admin_message` | Broadcast message from admin |
| `pong` | Response to ping |

##### `connected` Message
```json
{
  "type": "connected",
  "data": {
    "tournament_status": { ... },
    "tables": [ ... ]
  }
}
```

#### Messages TO Server (Viewer Sends)

| Message | Description |
|---------|-------------|
| `ping` | Keep-alive ping (responds with `pong`) |

---

## Admin API Endpoints

All admin endpoints are prefixed with `/admin` and require HTTP Basic Authentication.

**Authentication:** HTTP Basic Auth with admin password configured in server settings.

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/status` | GET | Get detailed tournament status |
| `/admin/players` | GET | Get list of all registered players |
| `/admin/tables` | GET | Get state of all active tables |
| `/admin/start` | POST | Start the tournament |
| `/admin/pause` | POST | Pause the tournament |
| `/admin/resume` | POST | Resume a paused tournament |
| `/admin/reset` | POST | Reset tournament (keeps registrations) |
| `/admin/kick/{player_id}` | POST | Kick a player from tournament |
| `/admin/player/{player_id}` | DELETE | Remove a player from registration |
| `/admin/broadcast` | POST | Broadcast message to all clients |

### Admin WebSocket

**Endpoint:** `ws://<host>/admin/ws`

Connect to receive real-time admin updates.

#### Messages FROM Server (Admin Receives)

| Type | Description |
|------|-------------|
| `status` | Initial tournament status on connect |
| `game_state` | Updated game state from all tables |
| `elimination` | Player elimination notification |
| `tournament_complete` | Tournament has ended |

##### `status` Message
```json
{
  "type": "status",
  "data": {
    "tournament_id": "...",
    "name": "Poker Tournament",
    "status": "running",
    "registered_players": 10,
    "remaining_players": 8,
    "active_tables": 2,
    "hands_played": 25,
    "current_blinds": { "small": 10, "big": 20 }
  }
}
```

---

## WebSocket Message Types Summary

### All Message Types (Server → Client)

| Type | Recipients | Description |
|------|------------|-------------|
| `connected` | Bot, Viewer | Initial connection confirmation |
| `status` | Admin | Tournament status update |
| `game_state` | Bot, Viewer, Admin | Game state update |
| `action_result` | Bot | Result of submitted action |
| `table_change` | Bot | Player moved to new table |
| `elimination` | Bot, Viewer, Admin | Player eliminated |
| `tournament_complete` | Bot, Viewer, Admin | Tournament finished |
| `kicked` | Bot | Player kicked from tournament |
| `admin_message` | Bot, Viewer | Broadcast from admin |
| `pong` | Bot, Viewer | Response to ping |
| `error` | Bot | Error message |

### All Message Types (Client → Server)

| Type | Senders | Description |
|------|---------|-------------|
| `action` | Bot | Submit poker action |
| `ping` | Bot, Viewer | Keep-alive ping |
