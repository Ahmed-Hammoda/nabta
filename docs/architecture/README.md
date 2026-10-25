# System architecture

**Owner:** Ahmed Hamouda

![Nabta system architecture](architecture.svg)

Nabta runs on a **single Raspberry Pi** placed next to the plant. The sensors and the pump connect directly to it, and the same board stores the data, runs the AI assistant and serves the dashboard.

In phase 1 everything runs locally: **no internet connection is needed**.

---

## Components

| Component | Runs on | Role |
|---|---|---|
| Sensors | Connected to the Pi | Soil moisture, air temperature and humidity, light, water tank level |
| Relay + pump | Connected to the Pi | Waters the plant |
| Hardware control | Raspberry Pi | Reads the sensors every 30 s, drives the pump, enforces a pump timeout |
| Backend server | Raspberry Pi | Stores readings, runs the decision cycle, serves the dashboard |
| Database | Raspberry Pi | Sensor readings, AI decisions with their explanations, chat history |
| AI assistant | Raspberry Pi | Small language model (local) + plant knowledge base: decides, explains, answers questions |
| Safety layer | Raspberry Pi | Hard rules that check every action before it reaches the pump |
| Web dashboard | User's browser | Plant status, history charts, watering log, chat with the assistant |
| Cloud LLM API | Internet (phase 2) | Same assistant on a cloud model, for the local vs. cloud comparison |

---

## Main flows

### 1. Monitoring
`Sensors → Hardware control → Backend → Database → Dashboard (live)`

### 2. Watering decision
1. The backend's scheduler wakes up periodically (and when moisture drops sharply).
2. It sends the AI the **context**: latest readings, recent history, last watering, plant profile.
3. The AI answers with a **proposed action** (water X seconds / don't water) and a short explanation.
4. The **safety layer** checks it against the hard rules and approves, shortens or rejects it.
5. An approved command goes to the hardware control, which runs the pump.
6. The decision and its explanation are stored and shown in the watering log.

### 3. User chat
`User → Dashboard → Backend → AI (with plant data + knowledge base) → answer → Dashboard`

---

## Key design decisions

- **One board for everything.** Fewer parts, simpler wiring and no device-to-device communication to debug.
- **The AI proposes, the rules decide.** The language model never controls the pump directly; every action passes the safety layer.
- **Two levels of failsafe.** The safety layer filters every decision, and the hardware control stops the pump after a maximum run time no matter what.
- **Local first.** The assistant runs on a small local model so Nabta works without internet; the cloud API is added in phase 2 only for comparison.
- **Same interface for local and cloud models.** The backend talks to the AI through one interface, so switching between the local model and the cloud API is a configuration change.
