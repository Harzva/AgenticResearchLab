# Research method

AgenticResearchLab separates research ideation into six auditable stages.

## 1. Understand the non-agent baseline

Describe the task, environment, inputs, outputs, failure modes, and strongest deterministic or single-model solution before proposing an agent.

## 2. Establish agentic necessity

An Agentic method should need sequential state, environment feedback, adaptive decisions, tools, memory, verification, or coordination. If a fixed pipeline is sufficient, an agent adds complexity without a research contribution.

## 3. Retrieve the nearest work

Search by task, environment, action space, architecture, supervision, evaluation, and failure mode. The closest method is not always the one sharing the most title words.

## 4. Form a falsifiable novelty claim

Use the form:

> Existing systems fail under **condition X** because of **mechanism Y**. We introduce **component Z**, which should improve **measurable outcome M** without an unacceptable increase in **cost or risk C**.

## 5. Design experiments with the claim

Every claim needs:

- a relevant benchmark or a justified new environment;
- a deterministic and single-agent baseline;
- the closest published Agentic baseline;
- component ablations;
- equalized model and inference budgets where possible;
- task success, process quality, cost, latency, safety, and recovery metrics.

## 6. Run rejection gates

Before writing a paper, ask:

- Is this merely prompt engineering or role renaming?
- Does extra inference compute explain all gains?
- Is the evaluation reproducible across app versions and device configurations?
- Are success detectors independent of the evaluated model?
- Does the method recover from errors or only succeed on clean trajectories?
- Are privacy and irreversible actions handled explicitly?
