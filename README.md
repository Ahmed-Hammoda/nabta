# Nabta – AI Smart Irrigation Assistant

> A smart plant-care device that watches over a plant around the clock and waters it only when it truly needs it.

Nabta senses the soil, air and light conditions of a plant, decides the right moment and amount of water, and explains its decisions in simple language. Users follow their plant's health from a dashboard and can ask the assistant questions such as *"Is my plant okay?"* or *"Why did you water today?"*. Designed with Tunisia's water scarcity in mind, Nabta helps farmers and home gardeners save water while keeping plants healthy.

**Course:** CS496 – AI Engineering, Mediterranean Institute of Technology (MEDTECH)

---

## Objectives

1. **Save water** by watering only when the plant needs it, instead of on a fixed schedule.
2. **Keep plants healthy** by detecting stress (dryness, heat, poor light) before it causes damage.
3. **Make plant care effortless** so the user doesn't have to remember or guess when to water.
4. **Give clear, trustworthy advice** in plain language the user can understand and act on.
5. **Keep the user informed** with a simple view of the plant's condition and history at any time.
6. **Operate safely and reliably**, never over-watering and always behaving predictably.
7. **Be affordable and accessible** for small farmers and home gardeners in Tunisia.
8. **Look good at home** with a friendly design inspired by Tunisian identity.

---

## How it works (overview)

```
Sensors ──► Raspberry Pi ──► Dashboard + chat
               │   (small language model + safety rules)
               ▼
             Pump
```

- **Sensors** measure soil moisture, temperature, humidity and light.
- **The Raspberry Pi** reads the sensors, stores the data and runs a small language model locally, so the assistant works without internet.
- **The AI assistant** decides whether to water, explains why, and answers questions. Hard safety rules always have the final word.
- **Later phase:** the same assistant is connected to a cloud AI API and compared with the local model.

See [`docs/architecture/`](docs/architecture/) for the detailed architecture. A second option runs the AI model on a PC (with GPU) that the Raspberry Pi calls over Wi-Fi.

---

## Repository structure

| Folder | Content | Owner |
|---|---|---|
| [`docs/`](docs/) | Architecture, plant research, meeting notes, report | Everyone |
| [`hardware/`](hardware/) | Components, wiring diagrams, firmware | Aymen Saad |
| [`enclosure/`](enclosure/) | 3D design files and renders | Youssef Ben Moussa |
| [`ai/`](ai/) | Assistant behavior, prompts, knowledge base, evaluation | Ahmed Hamouda |
| [`backend/`](backend/) | Server that connects sensors, AI and dashboard | Ahmed Hamouda |
| [`dashboard/`](dashboard/) | User dashboard and chat interface | Ahmed Ridha Melayah |
| [`docs/plant-research/`](docs/plant-research/) | Target plant family and its needs | Yassine Mtibaa |

---

## Team

| Member | Role |
|---|---|
| Ahmed Hamouda | AI assistant and system architecture |
| Aymen Saad | Hardware and components |
| Ahmed Ridha Melayah | Dashboard |
| Youssef Ben Moussa | 3D design and enclosure |
| Yassine Mtibaa | Plant research |

---

## Roadmap

- [x] Week 1 – Project definition, task split, main decisions
- [ ] Week 2 – Hardware working, plant family chosen, architecture finalized
- [ ] Week 3 – Local AI assistant connected to live sensor data
- [ ] Week 4 – Dashboard, cloud AI API, local vs. API comparison
- [ ] Week 5 – Enclosure assembly, final testing, report and demo

---

## Contributing

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before pushing anything.
