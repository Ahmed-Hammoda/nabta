# System architecture

**Owner:** Ahmed Hamouda

![Nabta system architecture](architecture.svg)

Nabta is split into two physical parts:

- a **sensor node** (ESP32) next to the plant, which measures and acts;
- an **edge hub** (Raspberry Pi 5, 8 GB), which stores data, thinks and talks to the user.

In phase 1 everything runs on the local network: **no internet connection is needed**.

---

## Components

| Component | Runs on | Role |
|---|---|---|
| Sensors | ESP32 | Soil moisture, air temperature and humidity, light, water tank level |
| ESP32 firmware | ESP32 | Reads sensors every 30 s, publishes them, executes pump commands, enforces a local pump timeout |
| Relay + pump | ESP32 | Waters the plant |
| MQTT broker | Raspberry Pi | Message channel between the ESP32 and the server |
| Backend server | Raspberry Pi | Receives readings, stores them, runs the decision cycle, serves the dashboard |
| Database | Raspberry Pi | Sensor readings, AI decisions with their explanations, chat history |
| AI assistant | Raspberry Pi | Small language model (local) + plant knowledge base: decides, explains, answers questions |
| Safety layer | Raspberry Pi | Hard rules that check every action before it reaches the pump |
| Web dashboard | User's browser | Plant status, history charts, watering log, chat with the assistant |
| Cloud LLM API | Internet (phase 2) | Same assistant on a cloud model, for the local vs. cloud comparison |

---

## Main flows

### 1. Monitoring
`Sensors → ESP32 → MQTT → Backend → Database → Dashboard (live)`

### 2. Watering decision
1. The backend's scheduler wakes up periodically (and when moisture drops sharply).
2. It sends the AI the **context**: latest readings, recent history, last watering, plant profile.
3. The AI answers with a **proposed action** (water X seconds / don't water) and a short explanation.
4. The **safety layer** checks it against the hard rules and approves, shortens or rejects it.
5. An approved command goes through MQTT to the ESP32, which runs the pump.
6. The decision and its explanation are stored and shown in the watering log.

### 3. User chat
`User → Dashboard → Backend → AI (with plant data + knowledge base) → answer → Dashboard`

---

## Key design decisions

- **The AI proposes, the rules decide.** The language model never controls the pump directly; every action passes the safety layer.
- **Two levels of failsafe.** Even if the Raspberry Pi crashes, the ESP32 stops the pump after a maximum run time on its own.
- **Local first.** The assistant runs on a small local model so Nabta works without internet; the cloud API is added in phase 2 only for comparison.
- **MQTT between devices.** Lightweight, standard for IoT, and lets more sensor nodes (more plants) be added later without changing the hub.
- **Same interface for local and cloud models.** The backend talks to the AI through one interface, so switching between the local model and the cloud API is a configuration change.
