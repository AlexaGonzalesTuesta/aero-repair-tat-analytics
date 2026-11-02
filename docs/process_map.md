# Repair Value Stream: Current State and Future State

## Current state (as-is)
Red stages are where the data shows the most waiting and rework.

```mermaid
flowchart LR
    A[Receiving] --> B[Inspection]
    B --> C[Teardown and Evaluation]
    C --> D{Customer quote approval}
    D -->|Approved| E{Parts available?}
    E -->|No| F[Awaiting Parts]
    F --> G[Repair]
    E -->|Yes| G
    G --> H[Reassembly]
    H --> I{Test}
    I -->|Fail| J[Rework] --> I
    I -->|Pass| K[Final QA and Return to Service paperwork]
    K --> L[Ship to customer]

    style D fill:#fde2d6,stroke:#eb6834
    style F fill:#fde2d6,stroke:#eb6834
    style J fill:#fde2d6,stroke:#eb6834
```

**Pain points found in the data**
1. **Awaiting Parts** is the largest single stage of repair time and the primary cause of most late orders.
2. **Customer quote approval** is the second largest cause of late orders, worst for defense customers.
3. **Test failures** send units back through repair, adding rework time and hurting first-pass yield.

## Future state (to-be)

```mermaid
flowchart LR
    A[Receiving + intake risk score] --> B[Inspection]
    B --> C[Teardown and Evaluation]
    C --> D{Within pre-approved not-to-exceed limit?}
    D -->|Yes, auto-approved| E{Parts available?}
    D -->|No| D2[Customer quote approval] --> E
    E -->|No| F[Expedite from safety stock or second source]
    F --> G[Repair]
    E -->|Yes| G
    G --> H[Reassembly with standard work checklist]
    H --> I{Test}
    I -->|Fail| J[Rework + root cause logged] --> I
    I -->|Pass| K[Final QA and RTS paperwork]
    K --> L[Ship to customer]

    style A fill:#d6e6fa,stroke:#2a78d6
    style D fill:#d6e6fa,stroke:#2a78d6
    style F fill:#d6e6fa,stroke:#2a78d6
    style H fill:#d6e6fa,stroke:#2a78d6
```

| Change | Targets | Owner |
|---|---|---|
| Intake risk score flags likely-late orders on day 1 | Proactive expediting and customer communication | Customer support + repair leads |
| Pre-approved not-to-exceed repair limits | Quote approval wait | Contracts / account managers |
| Safety stock and dual-sourcing for chronic shortage part numbers | Awaiting Parts wait | Supply chain |
| Standard work checklist before Test | Rework and first-pass yield | Repair engineering |
