# Agentic research opportunity report

## Subject

手机端隐私感知的长期记忆智能体

## Evidence retrieved

- [A3: Android Agent Arena for Mobile GUI Agents](https://arxiv.org/abs/2501.01149) — Evaluates mobile agents on real-world third-party apps and practical online tasks.
- [K²-Agent: Co-Evolving Know-What and Know-How for Hierarchical Mobile Device Control](https://iclr.cc/virtual/2026/poster/10011138) — Co-evolves task knowledge and procedural skills for hierarchical mobile control.
- [MobileUse: A GUI Agent with Hierarchical Reflection for Autonomous Mobile Operation](https://arxiv.org/abs/2507.16853) — Combines hierarchical reflection and proactive exploration for long-horizon Android operation.
- [M²-Miner: Multi-Agent Enhanced MCTS for Mobile GUI Agent Data Mining](https://arxiv.org/abs/2602.05429) — Combines multi-agent roles and Monte Carlo tree search to mine mobile GUI trajectories.
- [Mobile-Agent: Autonomous Multi-Modal Mobile Device Agent with Visual Perception](https://arxiv.org/abs/2401.16158) — Vision-centric mobile operation without relying on app XML or system metadata.
- [Benchmarking Agent Memory in Interdependent Multi-Session Agentic Tasks](https://icml.cc/virtual/2026/poster/64842) — Existing evaluations of agents with memory typically assess memorization and action in isolation. One class of benchmarks evaluates memorization by testing recall of past conversations or text but fails to capture how memory is used to guide future decisions. Another class focuses on agents acting in single-session tasks without the need for long-term memory. However, in realistic settings, memorization and action are tightly coupled: agents acquire memory while interacting with the environment,
- [Executable Agentic Memory for GUI Agent](https://icml.cc/virtual/2026/poster/65931) — Modern GUI agents typically rely on a model-centric and step-wise interaction paradigm, where LLMs must re-interpret the UI and re-decide actions at every screen, which is fragile in long-horizon tasks. In this paper, we propose Executable Agentic Memory (EAM), a structured Knowledge Graph (KG) that shifts GUI planning from free-form generation to a robust retrieval-and-execution process. Our approach includes a sample-efficient memory construction pipeline using state-aware DFS and action-group
- [GhostEI-Bench: Do Mobile Agent Resilience to Environmental Injection in Dynamic On-Device Environments?](https://iclr.cc/virtual/2026/poster/10011688) — Vision-Language Models (VLMs) are increasingly deployed as autonomous agents to navigate mobile Graphical User Interfaces (GUIs). However, their operation within dynamic on-device ecosystems, which include notifications, pop-ups, and inter-app interactions, exposes them to a unique and underexplored threat vector: environmental injection. Unlike traditional prompt-based attacks that manipulate textual instructions, environmental injection contaminates the agent's visual perception by inserting a
- [MemEvolve: Meta-Evolution of Agent Memory Systems](https://icml.cc/virtual/2026/poster/61379) — Self-evolving memory systems are rapidly reshaping the evolutionary paradigm of large language model (LLM)-based agents. Prior work has predominantly relied on manually engineered memory architectures to store trajectories, distill experience, and synthesize reusable tools, enabling agents to evolve on the fly within environment interactions. However, this paradigm is fundamentally constrained by the \textit{staticity} of the memory system itself: while memory facilitates agent-level evolving, t
- [Learning to Share: Selective Memory for Efficient Parallel Agentic Systems](https://icml.cc/virtual/2026/poster/62890) — Agentic systems solve complex tasks by coordinating multiple agents that iteratively reason, invoke tools, and exchange intermediate results. To improve robustness and solution quality, recent approaches deploy multiple agent teams running in parallel to explore diverse reasoning trajectories. However, parallel execution comes at a significant computational cost: when different teams independently reason about similar sub-problems or execute analogous steps, they repeatedly perform substantial o

## Current capability signals

Detected dimensions: efficiency-deployment, memory-reflection, personalization-privacy.

## Candidate research upgrades

1. 融合截图、UI 树和可交互区域，并评测跨分辨率、主题、语言与布局泛化。
2. 拆分规划、执行、进度管理和纠错角色，验证多 Agent 是否确有必要。
3. 构造环境注入、UI 异常和误操作风险模型，让 Agent 在执行前后进行安全验证。
4. 把贡献绑定到可复现移动环境、过程级检查点和任务成功验证器，而非只用主观案例。

## Required rejection gates

- Agentic necessity: show why a deterministic workflow or single model is insufficient.
- Novelty: compare each claim against the closest retrieved work, not against a generic baseline.
- Evaluation: define executable tasks, success predicates, cost, latency, safety, and recovery metrics.
- Ablation: isolate planning, memory, reflection, tools, multi-agent roles, and extra inference compute.
- Reproducibility: freeze apps, device configuration, model versions, prompts, and task seeds.
