# Awesome Mobile Agentic AI

> Papers, benchmarks, datasets, and open-source systems for agents that perceive, reason, and act on smartphones and mobile GUIs.

Machine-readable source: `src/agentic_research_lab/data/topics.json`.
Entries are evidence-linked and intentionally distinguish mobile-specific work from general GUI foundations.

## Contents

- [Mobile agents and methods](#mobile-agents-and-methods)
- [Benchmarks and datasets](#benchmarks-and-datasets)
- [Open-source mobile systems](#open-source-mobile-systems)
- [Cross-platform GUI foundations](#cross-platform-gui-foundations)
- [Related awesome lists](#related-awesome-lists)

## Mobile agents and methods

- **M²-Miner: Multi-Agent Enhanced MCTS for Mobile GUI Agent Data Mining** — Combines multi-agent roles and Monte Carlo tree search to mine mobile GUI trajectories. ([paper](https://arxiv.org/abs/2602.05429))
  - `2026 · ICLR 2026` · tags: MCTS, data mining, multi-agent, trajectory
- **Mobile-Agent-RAG: Driving Smart Multi-Agent Coordination with Contextual Knowledge Empowerment for Long-Horizon Mobile Automation** — Uses retrieval-augmented contextual knowledge to coordinate agents over long mobile workflows. ([paper](https://ojs.aaai.org/index.php/AAAI/article/view/40241))
  - `2026 · AAAI 2026` · tags: RAG, coordination, long-horizon, knowledge
- **K²-Agent: Co-Evolving Know-What and Know-How for Hierarchical Mobile Device Control** — Co-evolves task knowledge and procedural skills for hierarchical mobile control. ([paper](https://iclr.cc/virtual/2026/poster/10011138))
  - `2026 · ICLR 2026` · tags: skill learning, hierarchical control, knowledge evolution, mobile
- **EcoAgent: An Efficient Device-Cloud Collaborative Multi-Agent Framework for Mobile Automation** — Explores device-cloud collaboration and efficient multi-agent routing for mobile automation. ([paper](https://ojs.aaai.org/index.php/AAAI/article/view/40230))
  - `2026 · AAAI 2026` · tags: device-cloud, efficiency, multi-agent, automation
- **Agent-SAMA: State-Aware Mobile Assistant** — Studies state-aware assistance and specialized agent roles for mobile interaction. ([paper](https://ojs.aaai.org/index.php/AAAI/article/view/40187))
  - `2026 · AAAI 2026` · tags: state awareness, assistant, multi-agent, mobile
- **MobileUse: A GUI Agent with Hierarchical Reflection for Autonomous Mobile Operation** — Combines hierarchical reflection and proactive exploration for long-horizon Android operation. ([paper](https://arxiv.org/abs/2507.16853) · [code](https://github.com/MadeAgents/mobile-use))
  - `2025 · arXiv · MIT` · tags: hierarchical reflection, exploration, long-horizon, android
- **Mobile-Agent-v3: Foundamental Agents for GUI Automation** — Pairs GUI-Owl foundation models with planning, progress management, reflection, memory, and scalable environment RL. ([paper](https://arxiv.org/abs/2508.15144) · [code](https://github.com/X-PLUG/MobileAgent))
  - `2025 · arXiv · MIT` · tags: GUI-Owl, multi-agent, reinforcement learning, cross-platform
- **Advancing Mobile GUI Agents: A Verifier-Driven Approach to Practical Deployment** — Uses an LLM verifier to rank candidate actions, with progress preferences and deployment-oriented latency. ([paper](https://arxiv.org/abs/2503.15937))
  - `2025 · arXiv` · tags: verifier, action ranking, latency, deployment
- **Mobile-Agent: Autonomous Multi-Modal Mobile Device Agent with Visual Perception** — Vision-centric mobile operation without relying on app XML or system metadata. ([paper](https://arxiv.org/abs/2401.16158) · [code](https://github.com/X-PLUG/MobileAgent))
  - `2024 · ICLR 2024 Workshop · MIT` · tags: visual perception, planning, tool use, Mobile-Eval
- **Mobile-Agent-v2: Mobile Device Operation Assistant with Effective Navigation via Multi-Agent Collaboration** — Separates planning, decision, reflection, and progress memory for long mobile tasks. ([paper](https://arxiv.org/abs/2406.01014) · [code](https://github.com/X-PLUG/MobileAgent))
  - `2024 · NeurIPS 2024 · MIT` · tags: multi-agent, planning, reflection, memory
- **Empowering LLM to Use Smartphone for Intelligent Task Automation** — AutoDroid combines Android UI exploration, app memory, and LLM planning for task automation. ([paper](https://arxiv.org/abs/2308.15272) · [code](https://github.com/MobileLLM/AutoDroid))
  - `2023 · arXiv · MIT` · tags: AutoDroid, memory, ui hierarchy, adb
- **AppAgent: Multimodal Agents as Smartphone Users** — Learns to operate unfamiliar smartphone apps through autonomous exploration or human demonstrations. ([paper](https://arxiv.org/abs/2312.13771) · [code](https://github.com/TencentQQGYLab/AppAgent))
  - `2023 · arXiv · MIT` · tags: exploration, demonstration, app knowledge, android

## Benchmarks and datasets

- **MobileSafetyBench: Evaluating Safety of Autonomous Agents in Mobile Device Control** — Evaluates safety risks arising from autonomous control of mobile devices. ([paper](https://ojs.aaai.org/index.php/AAAI/article/view/41090))
  - `2026 · AAAI 2026` · tags: safety, risk, device control, benchmark
- **GhostEI-Bench: Do Mobile Agents Resist Environmental Injection in Dynamic On-Device Environments?** — Studies environmental injection attacks in dynamic on-device mobile settings. ([paper](https://arxiv.org/abs/2510.20333))
  - `2026 · ICLR 2026` · tags: environmental injection, security, dynamic environment, robustness
- **FingerTip 20K: A Benchmark for Proactive and Personalized Mobile LLM Agents** — Targets proactive and personalized behavior rather than instruction-only mobile control. ([paper](https://arxiv.org/abs/2507.21071))
  - `2026 · ICLR 2026` · tags: personalization, proactive agent, benchmark, user modeling
- **MobileWorld: Benchmarking Autonomous Mobile Agents in Agent-User Interactive and MCP-Augmented Environments** — Adds long cross-app tasks, user interaction, MCP calls, and functional verification beyond AndroidWorld. ([paper](https://arxiv.org/abs/2512.19432) · [code](https://github.com/Tongyi-MAI/MobileWorld))
  - `2025 · ACL 2026 · Apache-2.0` · tags: MCP, user interaction, cross-app, long-horizon
- **A3: Android Agent Arena for Mobile GUI Agents** — Evaluates mobile agents on real-world third-party apps and practical online tasks. ([paper](https://arxiv.org/abs/2501.01149))
  - `2025 · arXiv` · tags: arena, third-party apps, online tasks, mobile
- **Mobile-Bench: An Evaluation Benchmark for LLM-based Mobile Agents** — Covers single- and multi-app tasks and introduces process checkpoints for planning evaluation. ([paper](https://arxiv.org/abs/2407.00993) · [code](https://github.com/XiaoMi/MobileBench))
  - `2024 · arXiv · license-review-required` · tags: multi-app, API, checkpoint, planning
- **LlamaTouch: A Faithful and Scalable Testbed for Mobile UI Task Automation** — Evaluates task completion through essential application and system states on real mobile environments. ([paper](https://arxiv.org/abs/2404.16054) · [code](https://github.com/LlamaTouch/LlamaTouch))
  - `2024 · arXiv · license-not-declared` · tags: testbed, essential states, on-device, evaluation
- **B-MoCA: Benchmarking Mobile Device Control Agents across Diverse Configurations** — Randomizes layouts, languages, wallpapers, and device types to test configuration generalization. ([paper](https://arxiv.org/abs/2404.16660) · [code](https://github.com/jylee425/b-moca))
  - `2024 · CoLLAs 2025 · Apache-2.0` · tags: generalization, configuration, android, robustness
- **AndroidWorld: A Dynamic Benchmarking Environment for Autonomous Agents** — A reproducible Android environment with dynamically instantiated tasks and executable success checks. ([paper](https://arxiv.org/abs/2405.14573) · [code](https://github.com/google-research/android_world))
  - `2024 · ICLR 2025 · Apache-2.0` · tags: android, dynamic tasks, reproducibility, evaluation
- **AndroidLab: Training and Systematic Benchmarking of Android Autonomous Agents** — Provides Android environments, 138 tasks, unified action spaces, and Android Instruct training data. ([paper](https://arxiv.org/abs/2410.24024) · [code](https://github.com/THUDM/Android-Lab))
  - `2024 · arXiv · MIT` · tags: training, benchmark, android instruct, emulator

## Open-source mobile systems

- **UFO MobileAgent** — Android task executor using UI controls, screenshots, app management, MCP, and a finite-state control loop. ([code](https://github.com/microsoft/UFO))
  - `2026 · MIT` · tags: MCP, state machine, ADB, app management
- **MobileBench-OL** — Runs and evaluates multiple mobile GUI agents on physical Android devices with rule and XPath checks. ([code](https://github.com/xiaomi-research/mobilebench-ol))
  - `2026 · Apache-2.0` · tags: real device, uiautomator2, evaluation, trajectory
- **Mobile-Agent family** — Official implementation hub for Mobile-Agent, Mobile-Agent-v2/v3, GUI-Owl, data, models, and evaluations. ([code](https://github.com/X-PLUG/MobileAgent))
  - `2026 · MIT` · tags: framework, android, harmonyos, GUI-Owl

## Cross-platform GUI foundations

- **UI-Venus** — Screenshot-only native UI agent for grounding and navigation, evaluated on AndroidWorld and AndroidLab. ([code](https://github.com/inclusionAI/UI-Venus))
  - `2026 · license-not-declared` · tags: grounding, screenshot-only, navigation, VLA
- **UI-TARS** — Native end-to-end GUI agent models spanning perception, action modeling, reasoning, and reflective traces. ([code](https://github.com/bytedance/UI-TARS))
  - `2025 · Apache-2.0` · tags: native agent, grounding, reasoning, cross-platform
- **ShowUI** — Open end-to-end vision-language-action model for GUI grounding and computer use. ([code](https://github.com/showlab/ShowUI))
  - `2025 · CVPR 2025 · Apache-2.0` · tags: VLA, grounding, computer use, end-to-end
- **Aguvis** — Unified pure-vision agents for autonomous GUI interaction across platforms. ([code](https://github.com/xlang-ai/aguvis))
  - `2025 · ICML 2025 · license-not-declared` · tags: pure vision, GUI, action, foundation model
- **OS-Atlas** — Foundation action model and data pipeline for generalist GUI agents. ([code](https://github.com/OS-Copilot/OS-Atlas))
  - `2024 · Apache-2.0` · tags: action model, grounding, foundation model, GUI

## Related awesome lists

- **GUI Agents Paper List** — A broad GUI-agent bibliography with a dedicated mobile environment section. ([code](https://github.com/OSU-NLP-Group/GUI-Agents-Paper-List))
  - `2026 · license-not-declared` · tags: awesome list, survey, GUI agent, mobile
- **Awesome GUI Agents** — Curated GUI-agent resources, tools, frameworks, benchmarks, and mobile papers. ([code](https://github.com/ZJU-REAL/Awesome-GUI-Agents))
  - `2026 · license-not-declared` · tags: awesome list, GUI, tools, benchmarks

## Scope and contribution rules

- Mobile-specific work must execute on, train for, or evaluate smartphone/tablet environments.
- General GUI work belongs only in the cross-platform foundation section.
- A code link must point to the project's official or author-linked repository.
- Missing code, uncertain venue status, and non-standard licenses must be stated explicitly.
- Do not add a paper solely because it mentions a device or user interface in passing.
