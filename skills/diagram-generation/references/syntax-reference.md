# Mermaid syntax reference

## Flowchart

```mermaid
flowchart TD
  A[Rectangle] --> B(Rounded)
  B --> C([Stadium])
  C --> D[[Subroutine]]
  D --> E[(Database)]
  E --> F{Decision}
  F --> G{{Hexagon}}
  G --> H>Asymmetric]
  F -.->|dotted| I
  F ==>|thick| J
```

Directions: `TD`, `LR`, `RL`, `BT`.

## Sequence

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant A as API
  participant DB as Database
  U->>A: POST /orders
  A->>A: Validate
  A->>DB: INSERT
  DB-->>A: order_id
  A-->>U: 201 Created
  alt success
    A-->>U: body
  else failure
    A-->>U: 422
  end
```

`->>` call, `-->>` return, `->` async, `-->` async return.

## State

```mermaid
stateDiagram-v2
  [*] --> Draft
  Draft --> Review: submit
  Review --> Draft: request changes
  Review --> Published: approve
  Published --> [*]
```

## ERD

```mermaid
erDiagram
  CUSTOMER ||--o{ ORDER : places
  ORDER ||--|{ LINE_ITEM : contains
  CUSTOMER {
    string id PK
    string email
  }
```

## Class diagram

```mermaid
classDiagram
  class Animal {
    +String name
    +int age
    +speak()
  }
  Animal <|-- Dog
  Animal <|-- Cat
```

## Styling

```mermaid
flowchart TD
  A[Start] --> B[End]
  classDef primary fill:#3b82f6,stroke:#1d4ed8,color:#fff
  classDef warn fill:#f59e0b,stroke:#b45309,color:#fff
  class A primary
  class B warn
```

## Graphviz

```dot
digraph G {
  rankdir=LR;
  node [shape=box style=rounded];
  a -> b [label="edge"];
  {rank=same; a; b;}
}
```

`dot` for hierarchy, `sfdp` for large graphs, `circo` for circular layout.
