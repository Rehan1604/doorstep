# The ML in Doorstep

A task list could produce a mission. It could not do these three things.

## 1. A style bandit that learns you
Mission styles (stillness, steady walk, sensory hunt, close-up, together, detour) are the arms of a contextual Thompson-sampling bandit. Context is energy x group. After each mission, how you felt becomes a reward and updates a Beta posterior for that style. The next mission's style is sampled from those posteriors, and the card explains the pick. Pure Python, runs offline, per-browser data.

Synthetic-user simulation (`python ai/simulate_bandit.py`, 500 simulated people, 20 missions each, last 10 missions):

| Simulated people | Random | Bandit |
|---|---|---|
| Stable taste across contexts | picks their favourite 20% | 43% (avg reward 0.43 -> 0.51) |
| Different taste per context | 20% | 25% (barely better) |

This is a simulation, not a user study. With only a handful of missions per context, per-context taste is hard to learn; the model shares evidence across contexts (weight 0.8) because that helped most.

## 2. Embedding novelty guard
Every mission is embedded and compared by cosine similarity to your recent ones. A near-repeat triggers one regeneration with the closest title named as "must differ". The card shows how new the mission is.

## 3. Private semantic memory
Your typed notes are embedded. When you finish a mission, related earlier notes are retrieved and given to the model so the reflection can connect today to before.

## Embedders
- Local mode: `all-minilm` through Ollama (`ollama pull all-minilm`).
- Hosted mode or if the model is missing: a hashed bag-of-words and character-trigram vector. It is lexical: it matches shared words (heron/heron), not paraphrases. Vectors from different embedders are never compared.
- Similarity cut-offs were set by hand on a few examples, not tuned on real data.

## Privacy
Local mode: notes, vectors and learned preferences stay in the local SQLite file. Hosted demo: they live on the host's server, keyed to a random per-browser ID.