# AI assistant

**Owner:** Ahmed Hamouda

The brain of Nabta: it reads the plant's data, decides whether to water, explains its decisions and answers the user's questions.

## Folders

| Folder | Content |
|---|---|
| [`assistant-spec/`](assistant-spec/) | What the assistant does and must never do (behavior + safety rules) |
| [`prompts/`](prompts/) | System prompts and prompt versions |
| [`knowledge-base/`](knowledge-base/) | Documents about the plant family and irrigation, used to ground the AI's answers |
| [`evaluation/`](evaluation/) | Test scenarios and results: local model vs. cloud API |

## Phases

1. **Local:** a small language model running on the Raspberry Pi.
2. **Cloud:** the same assistant connected to a cloud AI API.
3. **Comparison:** both tested on the same scenarios (accuracy, response time, cost).
