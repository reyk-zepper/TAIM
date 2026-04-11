# TAIM — Team AI Manager (v2)

> **Your AI team. Your rules. Your control.**
>
> *1 Mitarbeiter = 10. Ein KI-gesteuertes Assistenzsystem, das wie ein ganzes Team arbeitet — und durch Nutzung besser wird.*

---

## Inhaltsverzeichnis

1. [Vision & Leitidee](#vision--leitidee)
2. [Problemstellung](#problemstellung)
3. [Positionierung & Marktanalyse](#positionierung--marktanalyse)
4. [Kernprinzipien](#kernprinzipien)
5. [Architekturübersicht](#architekturübersicht)
6. [Komponenten im Detail](#komponenten-im-detail)
   - [TAIM Conversation Layer](#1-taim-conversation-layer)
   - [TAIM Brain](#2-taim-brain)
   - [TAIM Orchestrator](#3-taim-orchestrator)
   - [TAIM Router](#4-taim-router)
   - [TAIM Rules Engine](#5-taim-rules-engine)
   - [TAIM Loop](#6-taim-loop)
   - [TAIM Dashboard](#7-taim-dashboard)
7. [Konzepte & Terminologie](#konzepte--terminologie)
8. [Datenarchitektur: TAIM Vault](#datenarchitektur-taim-vault)
9. [Multi-User & Team-Betrieb](#multi-user--team-betrieb)
10. [Deployment-Szenarien](#deployment-szenarien)
11. [Bestehende Bausteine](#bestehende-bausteine)
12. [Tech Stack](#tech-stack)
13. [Abgrenzung: Was TAIM nicht ist](#abgrenzung-was-taim-nicht-ist)
14. [Phasenplan](#phasenplan)
15. [Offene Entscheidungen](#offene-entscheidungen)
16. [Validierung & Konsistenzprüfung](#validierung--konsistenzprüfung)
17. [Lizenz & Philosophie](#lizenz--philosophie)

---

## Vision & Leitidee

TAIM ist ein **Assistenzsystem, das jedem Menschen ermöglicht, das Maximum aus KI herauszuholen** — unabhängig davon, wie tief das eigene technische Verständnis reicht. Es gibt dem Nutzer die Möglichkeit, KI-Agenten, Teams und Swarms zu steuern wie ein Dirigent ein Orchester leitet — ohne jedes Instrument selbst spielen zu können.

Die Kernidee: **Du sagst was du brauchst, TAIM liefert.** Nicht als Ticket-System, nicht als Firmen-Simulation, sondern als echter virtueller Assistent — ein ganzes Team, das bei Bedarf zuarbeitet, ausarbeitet, und dessen Arbeit du steuerst und kontrollierst.

**Der AI Equalizer:** Heute ist der produktive Umgang mit KI ein Expertenthema. Wer weiß wie man Prompts schreibt, Agenten konfiguriert, Modelle auswählt und Workflows orchestriert, bekommt exzellente Ergebnisse. Wer dieses Wissen nicht hat, bleibt hinter dem Möglichen zurück. TAIM schließt diese Lücke. Das Ziel ist nicht, dass jeder AI-Experte wird — das Ziel ist, dass jeder Experten-Ergebnisse bekommt. **AI lernt jeden, nicht jeder muss AI lernen.**

TAIM wird durch Nutzung besser. Je länger man damit arbeitet, desto mehr geht es auf individuelle Bedürfnisse ein. Ein persistentes Gedächtnis speichert Erkenntnisse, Präferenzen und optimierte Arbeitsweisen. Das System lernt — nicht durch Fine-Tuning eines Modells, sondern durch intelligente Akkumulation von Erfahrungswissen, optimierte Prompts und Few-Shot-Learning aus dem eigenen Memory. Ein Anfänger, der TAIM zwei Wochen nutzt, bekommt Ergebnisse auf dem Niveau eines Power-Users — weil TAIM gelernt hat, was er braucht und wie er arbeitet.

TAIM ist **Open Source**, **self-hosted**, **LLM-agnostisch** und **compliance-konfigurierbar**.

---

## Problemstellung

### Der Status Quo (2026)

KI-Agenten sind leistungsfähig geworden. Claude Code, Codex, OpenClaw — einzelne Agenten können beeindruckende Arbeit leisten. Aber der Weg von "KI existiert" zu "KI arbeitet produktiv für mich" ist für die meisten Menschen noch voller Hindernisse.

**Zugangshürde.** Die bestehenden Tools sind für Entwickler und AI-Experten gebaut. Um ein Multi-Agent-System aufzusetzen, muss man YAML-Konfigurationen schreiben, API-Keys verwalten, Modellunterschiede verstehen, Agent-Rollen definieren und Orchestrierungs-Logik begreifen. Das schließt den Großteil der Wissensarbeiter aus — Marketingmanager, Berater, Projektleiter, Kreative, Unternehmer — die enormen Nutzen aus KI-Teams ziehen könnten, aber nicht die technische Tiefe mitbringen.

**Fragmentierung.** Jeder Agent läuft isoliert. Claude Code weiß nicht, was Codex gerade tut. OpenClaw kennt die Ergebnisse eines CrewAI-Swarms nicht. Der Mensch wird zum manuellen Router zwischen KI-Systemen.

**Kontrollverlust.** Agenten laufen autonom, aber ohne zentrale Steuerung. Es gibt keine einfache Möglichkeit zu sagen: "Arbeite 4 Stunden an diesem Projekt und dann stopp." Budget-Überschreitungen und Endlos-Schleifen sind die Folge.

**Kein Gedächtnis.** Jede Session startet bei null. Gelernte Präferenzen, vergangene Entscheidungen, optimierte Workflows — alles verloren. Der Mensch muss jedes Mal von vorne briefen.

**Vendor Lock-in.** Die meisten Orchestrierungssysteme sind an einen LLM-Anbieter gebunden. Token-Kontingente aufgebraucht? Pech gehabt. Modell-Wechsel? Alles umbauen.

**Keine Compliance.** Im Business-Kontext braucht man konfigurierbare Regeln: Was darf ein Agent tun? Welche Daten darf er verarbeiten? Welche Standards müssen eingehalten werden? Bestehende Tools bieten das nicht oder nur rudimentär.

### Was fehlt

Ein System, das:
- **jedem** den Zugang zu KI-Teams ermöglicht, unabhängig vom technischen Wissensstand
- durch **natürliche Sprache** steuerbar ist — kein YAML, kein CLI, kein Konfigurationswissen nötig
- durch Nutzung **individuell besser** wird und sich an den User anpasst
- mehrere LLMs und Agenten **unter einer einheitlichen Steuerung** zusammenführt
- dem Nutzer **volle Kontrolle** über Dauer, Budget und Verhalten gibt
- im Business-Kontext mit **konfigurierbarer Compliance** einsetzbar ist
- **kein Vendor Lock-in** hat, **self-hosted** werden kann und **Open Source** ist

Das ist TAIM.

---

## Positionierung & Marktanalyse

### Bestehende Lösungen und ihre Lücken

| Tool | Was es tut | Was fehlt (für TAIMs Vision) |
|------|-----------|------------------------------|
| **Paperclip** | Orchestriert KI-Agenten als "Firma" mit Org-Charts, Budgets, Tickets | Ticket-basiert, Firmen-Metapher. Kein persistentes Lernen. Kein Multi-LLM-Failover. Technisches Setup nötig. |
| **OpenClaw** | Persönlicher KI-Assistent auf dem eigenen Rechner | Single-Agent. Keine Team-/Swarm-Orchestrierung. Kein Multi-User. Gute Zugänglichkeit, aber keine Team-Skalierung. |
| **CrewAI** | Rollenbasierte Multi-Agent-Orchestrierung | Framework ohne UI. Kein Dashboard. Kein Memory. Kein Compliance-Layer. Nur für Entwickler nutzbar. |
| **LangGraph** | Stateful Agent-Workflows als gerichtete Graphen | Komplex, entwicklerlastig. Kein Dashboard. Kein eingebautes Memory-System. Hohe Einstiegshürde. |
| **AutoGen/AG2** | Konversationelle Multi-Agent-Kollaboration | Token-intensiv. Kein UI. Kein Learning Loop. Erfordert Python-Kenntnisse. |
| **Dify.ai** | No-Code-Plattform für LLM-Apps mit visuellem Workflow-Builder | Gute Zugänglichkeit, aber Fokus auf Einzel-Workflows. Kein autonomes Multi-Agent-Teamwork. Kein Heartbeat. Kein Self-Learning. |

### TAIMs Differenzierung

1. **AI Equalizer** — Jeder Nutzer bekommt Experten-Ergebnisse, unabhängig vom technischen Wissensstand. Natürliche Sprache als primäres Interface, intelligente Defaults, kein Konfigurationswissen nötig.
2. **Assistent statt Firma** — Kein Ticket-System, kein Org-Chart. Ein intelligentes Team, das dir zuarbeitet.
3. **Multi-LLM mit intelligentem Failover** — Nutze Anthropic, OpenAI, lokale Modelle und wechsle transparent.
4. **Selbstlernendes Memory** — AI lernt den User, nicht umgekehrt. Das System wird durch Nutzung besser.
5. **Compliance by Configuration** — Regeln per Gespräch oder YAML definierbar.
6. **Zeitsteuerung** — "Arbeite 4 Stunden an diesem Projekt" ist ein erstklassiges Feature.
7. **Open Source & Self-Hosted** — Volle Kontrolle über Daten und Infrastruktur.

### Zielgruppe

- **Primär:** Jeder Wissensarbeiter der produktiver mit KI arbeiten will — Freelancer, Marketingmanager, Berater, Projektleiter, Kreative, Unternehmer. Kein technisches Vorwissen nötig.
- **Sekundär:** Technische Teams (1-15 Personen) die das Maximum an Kontrolle über ihre KI-Agenten wollen.
- **Tertiär:** Unternehmen die KI-Agenten unter Compliance-Anforderungen einsetzen müssen.

---

## Kernprinzipien

### 1. Conversation First
Der Hauptzugang zu TAIM ist natürliche Sprache. Der User beschreibt was er braucht, TAIM übersetzt das intern in Konfiguration und Aktionen. Kein YAML schreiben, kein CLI auswendig lernen, keine Modellnamen kennen. TAIM funktioniert wie ein erfahrener Teamleiter, den man briefen kann.

### 2. Progressive Disclosure
Alles hat intelligente Defaults. Ein neuer User muss null konfigurieren — er beschreibt seine Aufgabe und TAIM macht den Rest. Wer mehr Kontrolle will, kann tiefer einsteigen: YAML, CLI, API. Einfachheit ist der Default, Komplexität ist das Opt-in.

### 3. Control First
Der Mensch behält immer die Kontrolle. Approval-Gates bestimmen, wann menschliche Bestätigung nötig ist. Zeit- und Budget-Limits verhindern unkontrolliertes Laufen.

### 4. Learn by Use
TAIM wird besser durch Benutzung. Prompt-Optimization, Few-Shot-Learning aus dem Memory, akkumuliertes Erfahrungswissen. Kein Fine-Tuning nötig.

### 5. No Vendor Lock-in
Jedes LLM das eine API hat, kann genutzt werden. Der LLM-Router abstrahiert die Provider-Schicht vollständig.

### 6. Compile, Don't Search
Wissen wird vorab kompiliert, nicht zur Laufzeit durchsucht (noRAG-Philosophie). Das spart Tokens, erhöht die Qualität und macht alles auditierbar.

### 7. Transparency & Auditability
Alles ist in lesbaren Formaten gespeichert: Markdown, YAML, SQLite. Kein Black-Box-Verhalten.

### 8. Intelligent Scaling
Die richtige Menge Ressourcen für die richtige Aufgabe. TAIM wählt intelligent, wann ein einzelner Agent reicht und wann ein Swarm gebraucht wird.

---

## Architekturübersicht

```
┌──────────────────────────────────────────────────────────────────┐
│                         TAIM DASHBOARD                            │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │                  CONVERSATION LAYER                           │ │
│  │  Natürliche Sprache als primärer Zugang                       │ │
│  │  "Ich brauche eine Marktanalyse für unser Produkt..."         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Echtzeit-Monitoring · Agent-Status · Token-Tracking              │
│  Team-Verwaltung · Memory-Browser · Rules-Editor · Analytics      │
└───────────────────────────┬──────────────────────────────────────┘
                            │ REST API / WebSocket
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                     TAIM INTENT INTERPRETER                       │
│                                                                   │
│  Natürliche Sprache ──▶ Strukturierte Aufträge                   │
│  Smart Defaults ──▶ Fehlende Parameter ergänzen                  │
│  User-Memory ──▶ Kontext aus Erfahrung anreichern                │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                       TAIM ORCHESTRATOR                           │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ Agent        │  │ Team         │  │ Heartbeat               │ │
│  │ Registry     │  │ Composer     │  │ Manager                 │ │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ SWAT         │  │ Task         │  │ Iteration               │ │
│  │ Builder      │  │ Manager      │  │ Controller              │ │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘ │
└───────────────────────────┬──────────────────────────────────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
┌───────────────────┐ ┌──────────┐ ┌────────────────────┐
│   TAIM BRAIN      │ │ TAIM     │ │ TAIM RULES         │
│                   │ │ ROUTER   │ │ ENGINE              │
│ ┌───────────────┐ │ │          │ │                     │
│ │ Compiled      │ │ │ Multi-LLM│ │ Compliance-Profile  │
│ │ Knowledge     │ │ │ Provider │ │ laden, Regeln       │
│ │ (noRAG)       │ │ │ Mgmt +   │ │ durchsetzen,        │
│ ├───────────────┤ │ │ Failover │ │ Approval-Gates      │
│ │ Agent Memory  │ │ │          │ │ steuern             │
│ │ (claudianX)   │ │ │          │ │                     │
│ ├───────────────┤ │ │          │ │                     │
│ │ Session State │ │ │          │ │                     │
│ └───────────────┘ │ │          │ │                     │
└─────────┬─────────┘ └──────────┘ └─────────────────────┘
          │
          ▼
┌───────────────────┐
│   TAIM LOOP       │
│                   │
│ Learning Loop     │
│ Prompt-Optimizer  │
│ Pattern-Extraktor │
└───────────────────┘
```

---

## Komponenten im Detail

### 1. TAIM Conversation Layer

Der Conversation Layer ist TAIMs primärer Eingang. Er macht den Unterschied zwischen "ein Tool für Experten" und "ein Tool für jeden".

#### Das Prinzip: Reden statt Konfigurieren

Der User öffnet TAIM und sieht einen Chat. Er beschreibt was er braucht, in seinen eigenen Worten. TAIM versteht die Absicht, stellt Rückfragen wenn nötig, schlägt einen Plan vor, und setzt ihn nach Bestätigung um.

```
User:  "Ich brauche Hilfe bei einer Marktanalyse für unser 
        neues Produkt. Schau dir 5 Wettbewerber an und 
        erstelle mir einen Vergleichsreport."

TAIM:  "Ich stelle ein Research-Team zusammen:
        - 1 Lead-Researcher (koordiniert die Analyse)
        - 3 Web-Researcher (recherchieren parallel)  
        - 1 Analyst (wertet aus und erstellt den Report)
       
        Geschätzter Aufwand: ~2 Stunden, ~150k Tokens (~4,50€)
       
        Soll ich starten?"

User:  "Ja, aber maximal 3 Stunden und nicht mehr als 5 Euro."

TAIM:  "Verstanden. Limits gesetzt. Team startet jetzt.
        Ich melde mich wenn der Report fertig ist oder 
        wenn ich eine Rückfrage habe."
```

Der User hat nie eine YAML-Datei gesehen, nie "Agent Registry" gehört, nie ein Modell ausgewählt.

#### Intent Interpreter

Der Intent Interpreter übersetzt natürliche Sprache in strukturierte Aufträge:

```
Natürliche Sprache
    │
    ▼
Intent Interpreter
    ├── Aufgabe verstehen ("Marktanalyse für 5 Wettbewerber")
    ├── User-Memory laden (Präferenzen, vergangene ähnliche Aufträge)
    ├── Smart Defaults anwenden (Team-Größe, Modell-Tier, Iterationen)
    ├── Constraints extrahieren ("max 3h", "max 5€")
    ├── Rückfragen stellen wenn nötig ("Welche Wettbewerber?")
    │
    ▼
Strukturierter Auftrag ──▶ Orchestrator
```

Der Intent Interpreter nutzt selbst ein LLM (über den TAIM Router), braucht aber nur wenige Tokens — er muss die Absicht verstehen, nicht die Aufgabe ausführen.

#### Smart Defaults

Jede Entscheidung hat einen intelligenten Default. Der User muss nichts davon wissen, kann aber alles überschreiben:

| Entscheidung | Smart Default | User kann überschreiben |
|-------------|---------------|------------------------|
| Welches Team? | TAIM analysiert die Aufgabe und wählt passende Agenten | "Nimm nur einen Researcher" |
| Welches Modell? | Tier-basiert nach Aufgabenkomplexität | "Nimm das günstigste Modell" |
| Wie viele Iterationen? | 2-3 basierend auf Aufgabentyp | "Eine Runde reicht" |
| Zeitlimit? | Proportional zur geschätzten Komplexität | "Maximal 2 Stunden" |
| Token-Budget? | Basierend auf Erfahrungswerten aus dem Memory | "Nicht mehr als 10 Euro" |
| Output-Format? | Basierend auf User-Präferenzen aus dem Memory | "Mach einen PDF-Report" |

Je länger ein User mit TAIM arbeitet, desto besser werden die Smart Defaults — weil das Memory lernt, was der User typischerweise will.

#### Guided Onboarding

Beim ersten Start führt TAIM ein Gespräch statt ein Formular zu zeigen:

```
TAIM:  "Willkommen! Ich bin TAIM, dein KI-Team-Manager.
        Was für Arbeit machst du hauptsächlich?"

User:  "Ich bin Marketingmanager in einem SaaS-Startup."

TAIM:  "Gut — Content-Erstellung, Wettbewerber-Analyse und 
        Kampagnen-Planung werde ich gut abdecken können.
        
        Hast du eigene API-Keys für AI-Dienste wie OpenAI 
        oder Anthropic?"

User:  "Ich hab einen Anthropic API Key."

TAIM:  "Gibt es Regeln in deinem Unternehmen die ich beachten 
        muss? Datenschutz, Markenrichtlinien?"

User:  "Ja, DSGVO und unsere Markensprache nutzt immer 'Du'."

TAIM:  "Fertig eingerichtet:
        ✓ DSGVO-Compliance aktiv
        ✓ Alle Outputs nutzen 'Du'-Ansprache
        ✓ Claude als primäres Modell
        ✓ Marketing-optimierte Agent-Auswahl
        
        Sag mir einfach was du brauchst."
```

Aus diesem Gespräch generiert TAIM intern: Provider-Setup, Compliance-Regeln, User-Profil, Agent-Präferenzen. Der User hat nie ein Formular ausgefüllt.

#### Zwei Ebenen: Conversation & Configuration

```
┌────────────────────────────────────────────────────┐
│  EBENE 1: CONVERSATION LAYER (für jeden)            │
│                                                      │
│  Natürliche Sprache · Smart Defaults                 │
│  Guided Onboarding · TAIM erklärt was es tut         │
│                                                      │
│  "Erstelle mir eine Wettbewerber-Analyse"            │
│  "Stopp das Team, das reicht"                        │
│  "Warum hat das so lange gedauert?"                  │
└─────────────────────┬────────────────────────────────┘
                      │ Wer mehr will, steigt tiefer ein
                      ▼
┌────────────────────────────────────────────────────┐
│  EBENE 2: CONFIGURATION LAYER (für Power-User)      │
│                                                      │
│  YAML-Konfiguration · CLI · API-Zugriff              │
│  Manuelle Agent-Definitionen · Custom Rules          │
│  Direkte Modell-Auswahl · Prompt-Engineering         │
└────────────────────────────────────────────────────┘
```

Ebene 1 ist der Haupteingang. Ebene 2 ist das Escape Hatch für Experten. Alles was der Conversation Layer automatisch macht, kann in Ebene 2 überschrieben werden. Niemand wird gezwungen, Ebene 2 jemals zu betreten.

---

### 2. TAIM Brain

Das Brain ist TAIMs Wissenssystem in drei Schichten.

#### Schicht 1: Compiled Knowledge (basierend auf noRAG)

**Zweck:** Externes Wissen — Dokumente, Policies, Handbücher, Spezifikationen.

**Ansatz:** Dokumente werden einmal holistisch von einem LLM gelesen und in Compiled Knowledge Units (CKUs) übersetzt — strukturierte Fakten, Entitäten, Beziehungen, visuelle Inhaltsbeschreibungen, Zusammenfassungen. Gespeichert als YAML-Dateien, indiziert in einer SQLite Knowledge Map mit FTS5-Volltextsuche.

**Kein RAG.** Kein Chunking, keine Embeddings, keine Vektor-DB, keine Similarity Search. Compile, don't search.

**Warum das für LLMs besser ist:** Ein LLM das eine CKU bekommt, arbeitet mit vorverstandenem Wissen statt rohen Textfragmenten. 80-90% weniger Kontext-Tokens, keine Halluzinationen an Chunk-Grenzen, exakte Quellenangaben, visuelles Wissen als First-Class-Citizen.

**Technische Basis:** noRAG v1.0 (Apache 2.0, Python, 319 Tests, REST API, Watch Mode, Audit Log, Benchmark Kit).

**Für den User:** Er sagt im Chat "Hier ist unser Handbuch, bitte lern das." TAIM kompiliert im Hintergrund.

```
Dokument ──▶ Parser ──▶ LLM Compiler ──▶ CKU (YAML) ──▶ Knowledge Map (SQLite)
                                                                 │
Frage    ──▶ Router ──▶ Assembler ──▶ LLM ──▶ Antwort  ◀───────┘
```

#### Schicht 2: Agent Memory (basierend auf claudianX)

**Zweck:** Erfahrungswissen — User-Präferenzen, Entscheidungshistorie, gelernte Patterns, Agent-spezifisches Wissen.

**Ansatz:** Strukturierte Markdown-Notes mit Frontmatter, INDEX.md als Einstiegspunkt, Just-in-Time Retrieval. Bidirektional: User und Agenten arbeiten im selben Vault.

**Zwei Ebenen:**
- **Shared Memory:** Team-weites Wissen ("Bei API-Design immer OpenAPI-Spec zuerst")
- **Private Memory:** Pro User und pro Agent isoliert ("Reyk bevorzugt TypeScript")

**Technische Basis:** claudianX/codian Pattern, generalisiert für N Agenten/User, ohne Obsidian-Abhängigkeit. Dateiformat bleibt Obsidian-kompatibel.

**Für den User:** Das Memory arbeitet unsichtbar. Er merkt es daran, dass TAIM mit der Zeit besser wird. Im Dashboard kann er das Memory bei Bedarf einsehen und editieren.

#### Schicht 3: Session State

**Zweck:** Echtzeit-Kontext — laufende Tasks, Agent-Status, Zwischen-Ergebnisse.

**Ansatz:** Kurzlebig, in SQLite/in-memory. Wird nach Prozessende vom Learning Loop analysiert, relevante Erkenntnisse wandern in Schicht 2, Rest wird verworfen.

#### Context Assembler

Brücke zwischen Brain und LLM. Navigiert alle drei Schichten und baut minimalen Kontext:

```
Anfrage ──▶ Context Assembler
                ├── Compiled Knowledge: relevante CKUs
                ├── Agent Memory: Präferenzen, Patterns
                ├── Session State: aktueller Task-Kontext
                ├── Rules: geltende Compliance-Regeln
                ▼
            Minimaler Kontext (~200-800 Tokens statt ~3000-5000)
                ▼
              LLM ──▶ Antwort
```

---

### 3. TAIM Orchestrator

Execution-Engine hinter dem Conversation Layer. Verwaltet Agenten, baut Teams, steuert Ausführung.

#### Agent Registry

Zentrale Registry aller Agenten als Konfigurationsdateien:

```yaml
# agents/code-reviewer.yaml
name: "Code Reviewer"
description: "Reviews code for quality, security, and best practices"
model_preference: ["claude-sonnet-4-20250514", "gpt-4o"]
tools: [file_read, file_write, git_operations]
skills: [code_review, security_audit]
max_iterations: 5
requires_approval_for: [file_deletion, production_deployment]
```

Über den Conversation Layer muss der User die Registry nicht kennen — er beschreibt die Aufgabe und TAIM wählt die Agenten.

#### Team Composer

**Conversation-Zugang:** "Ich brauche ein Team das unsere Landing Page redesigned." → TAIM schlägt Team vor, User bestätigt.

**Configuration-Zugang:**
```yaml
# teams/frontend-redesign.yaml
name: "Frontend Redesign Team"
objective: "Redesign der Landing Page"
agents:
  - role: lead, agent: project-planner
  - role: developer, agent: frontend-dev
  - role: reviewer, agent: code-reviewer
time_budget: "4h"
token_budget: 500000
iteration_rounds: 3
```

**Automatisierter Team-Builder:** Analysiert Aufgabenbeschreibung und schlägt passendes Team vor.

#### SWAT Builder

SWAT (Spontaneous Work Assignment Team) — Ad-hoc-Teams die bei Bedarf gespawnt und nach Erledigung aufgelöst werden:

```
User: "Analysiere drei Wettbewerber-Websites, mach einen Report"
    ▼
SWAT Builder: 3x Web-Researcher + Analyst + Report-Writer → ~2h
    ▼
SWAT arbeitet, liefert, wird aufgelöst
    ▼
Erkenntnisse → Learning Loop
```

Für den User unsichtbar ob Team oder SWAT — TAIM entscheidet nach Aufgabentyp.

#### Heartbeat Manager

Steuert Aktivität und Lebenszyklus. Prüft ob Agenten arbeiten/hängen, reaktiviert bei Bedarf, trackt Fortschritt, setzt Limits durch.

**Zeitsteuerung per Conversation:** "Maximal 3 Stunden" → Heartbeat Manager setzt um.

```yaml
heartbeat:
  interval: 30s
  timeout: 120s
  time_limit: "4h"
  token_limit: 500000
  on_limit_reached: "graceful_stop"
```

#### Task Manager

Interne Arbeitseinheiten für Koordination. Kein Ticket-System — der User interagiert über den Conversation Layer auf Auftrags-Ebene.

#### Iteration Controller

Automatisierte Qualitätssicherung:

```
Agent arbeitet ──▶ Ergebnis ──▶ Review-Agent prüft ──▶ Feedback
                                        │
                              ┌─────────┤
                              ▼         ▼
                          Akzeptiert  Verbesserung nötig → nächste Iteration
```

Iterationsrunden per Smart Default oder User-Override. Frühzeitiger Abbruch wenn keine Verbesserung.

---

### 4. TAIM Router

Abstrahiert die LLM-Provider-Schicht. Multi-LLM-Betrieb mit intelligentem Failover.

#### Multi-Provider Management

```yaml
# config/providers.yaml
providers:
  - name: anthropic
    api_key_env: ANTHROPIC_API_KEY
    models: [claude-sonnet-4-20250514, claude-haiku-4-5-20251001]
    priority: 1
    monthly_budget: 100.00
  - name: openai
    api_key_env: OPENAI_API_KEY
    models: [gpt-4o, gpt-4o-mini]
    priority: 2
    monthly_budget: 50.00
  - name: ollama
    host: http://localhost:11434
    models: [qwen2.5:32b, llama3.1:70b]
    priority: 3
    cost: 0
```

**Für den User im Conversation Layer:** "Ich hab einen Anthropic Key und einen OpenAI Key" reicht. Oder: "Ich hab keinen API Key" → TAIM schlägt lokale Modelle via Ollama vor.

#### Intelligenter Failover

Wenn ein Provider sein Limit erreicht, wechselt der Router transparent zum nächsten:

```
Anfrage ──▶ Router
              ├── Anthropic verfügbar + Budget da? → Claude Sonnet
              ├── Nein → OpenAI verfügbar + Budget da? → GPT-4o
              └── Nein → Ollama lokal? → Qwen 32B (Fallback, $0)
```

#### Model Tiering

Automatische Modellwahl nach Aufgabenkomplexität:

- **Tier 1 (Premium):** Komplexes Reasoning, Architektur, Strategie → Claude Sonnet, GPT-4o
- **Tier 2 (Standard):** Code-Generierung, Textverarbeitung, Analyse → Claude Haiku, GPT-4o-mini
- **Tier 3 (Economy):** Klassifikation, Formatting, Routing → Lokale Modelle

Der User muss von Tiering nichts wissen. Power-User können überschreiben.

#### Token-Tracking & Statistik

Jeder API-Call wird protokolliert: Tokens, Kosten, Latenz, Fehlerraten, Failover-Events.

Im Dashboard als verständliche Übersicht: "Diesen Monat: 47 Aufträge, 23,40€, 2,1M Tokens."

---

### 5. TAIM Rules Engine

Konfigurierbare Verhaltensregeln — keine hardcodierten Guardrails, sondern flexible Regeln je nach Kontext.

#### Regeln per Conversation oder YAML

**Conversation-Zugang:**
```
User: "Wir müssen DSGVO-konform arbeiten. Keine Kundendaten 
       in Logs, und Kundendaten immer anonymisieren."

TAIM: "Zwei Compliance-Regeln angelegt:
       1. Keine personenbezogenen Daten in Logs (strikt)
       2. Kundendaten immer anonymisieren (strikt)
       Gelten ab sofort für alle Agenten."
```

**Configuration-Zugang:**
```yaml
# rules/compliance/dsgvo.yaml
name: "DSGVO Compliance"
scope: global
rules:
  - id: no-pii-in-logs
    description: "Keine personenbezogenen Daten in Logs"
    enforcement: strict
  - id: data-anonymization
    description: "Kundendaten immer anonymisieren"
    enforcement: strict
  - id: no-third-party-transfer
    description: "Kein Datentransfer an Dritte ohne Approval"
    enforcement: approval_required
```

#### Regel-Typen

- **Compliance-Regeln:** Was darf das System tun und was nicht? (DSGVO, ISO 27001, branchenspezifisch)
- **Verhaltens-Regeln:** Wie soll das System arbeiten? (Code-Standards, Markensprache, Qualität)
- **Approval-Gates:** Wann muss der Mensch bestätigen? (Löschungen, externe Kommunikation, Budget)

#### Regel-Loading

Regeln werden beim Session-Start geladen und dem Context Assembler übergeben. Agenten erhalten die für sie geltenden Regeln automatisch.

---

### 6. TAIM Loop

TAIMs Mechanismus zur Selbstverbesserung. Sitzt am Ende jedes Prozesses.

#### Learning Loop

```
Prozess endet
    │
    ▼
Loop analysiert:
    ├── Was hat gut funktioniert? → Pattern speichern
    ├── Was hat nicht funktioniert? → Anti-Pattern + Vermeidung
    ├── Welche Prompts waren effektiv? → Prompt-Cache mit Score
    ├── Welche Modell-Konfiguration war optimal? → Routing-Präferenz
    │
    └── Wohin speichern?
        ├── User-spezifisch  ──▶  users/{name}/memory/
        ├── Team-relevant    ──▶  shared/learning/
        └── System-relevant  ──▶  system/prompt-cache/
```

#### Prompt-Optimization

TAIM speichert Prompts mit Ergebnis-Qualität. Über die Zeit entsteht eine optimierte Bibliothek:

```yaml
# system/prompt-cache/code-review-v3.yaml
task_type: code_review
prompt_template: |
  Review the following code for:
  1. Security vulnerabilities
  2. Performance issues
  3. Adherence to {team_standards}
  Focus on {known_weak_areas} based on past reviews.
quality_score: 0.92
usage_count: 47
improvement_over_v2: "+15% issue detection rate"
```

#### Few-Shot Learning aus Memory

Bei neuen Aufgaben durchsucht der Context Assembler das Memory nach ähnlichen vergangenen Aufgaben und fügt deren Lösungen als Few-Shot-Beispiele ein. Das macht insbesondere den AI-Equalizer-Effekt möglich: Ein Anfänger profitiert von optimierten Prompts und Patterns, die das System über die Zeit gelernt hat.

---

### 7. TAIM Dashboard

Das Dashboard ist die Web-Oberfläche für TAIM. Der **Conversation Layer ist integraler Bestandteil** — kein separates Tool, sondern der zentrale Bereich des Dashboards.

#### Layout-Konzept

```
┌──────────────────────────────────────────────────────────┐
│  TAIM                                    [User] [Settings]│
├──────────┬───────────────────────────────────────────────┤
│          │                                               │
│  NAV     │   CONVERSATION LAYER (Hauptbereich)           │
│          │                                               │
│  Chat    │   User: "Erstelle eine Wettbewerber-Analyse"  │
│  Teams   │   TAIM: "Team wird zusammengestellt..."       │
│  Agents  │   TAIM: "Research-Team arbeitet (32 min)..."  │
│  Memory  │   TAIM: "Report fertig. Hier ist er."         │
│  Rules   │                                               │
│  Stats   │   [Eingabefeld: "Was brauchst du?"]           │
│  Audit   │                                               │
├──────────┴───────────────────────────────────────────────┤
│  Status: 3 Agenten aktiv · Budget: 4,20€/10€ · 1:32h    │
└──────────────────────────────────────────────────────────┘
```

#### Ansichten

**Chat (Hauptansicht):** Der Conversation Layer. Von hier aus wird TAIM primär gesteuert. Zeigt auch Statusmeldungen laufender Teams.

**Teams:** Aktive und gespeicherte Teams. Erstellen, starten, stoppen, konfigurieren. Für Ebene-2-User auch YAML-Editor.

**Agents:** Agent Registry durchsuchen. Für Ebene-2-User: eigene Agenten definieren.

**Memory:** Browser für Compiled Knowledge und Agent Memory. Editierbar. Hier kann der User TAIMs Wissen einsehen, korrigieren und ergänzen.

**Rules:** Aktive Compliance-Profile und Verhaltensregeln. Erstellen per Formular oder YAML.

**Stats:** Token-Verbrauch, Kosten, Qualitätsmetriken, Learning-Loop-Statistiken. Verständlich aufbereitet.

**Audit:** Chronologische Ansicht aller Aktionen. Filter nach Agent, Team, User, Zeitraum.

---

## Konzepte & Terminologie

| Konzept | Beschreibung |
|---------|-------------|
| **Agent** | Ein einzelner KI-Assistent mit Rolle, Modell-Präferenz und Toolset. Kann eigenständig oder im Team arbeiten. |
| **Team** | Persistente Gruppe von Agenten für ein Projekt. Definiertes Ziel, Budget, Zeitrahmen. |
| **Swarm** | Temporäre Gruppe für parallele Aufgaben. Wird nach Erledigung aufgelöst. |
| **SWAT** | Spontaneous Work Assignment Team — Ad-hoc-Team für eine einmalige Aufgabe, automatisch zusammengestellt. |
| **Heartbeat** | Regelmäßiges Signal zum Überwachen und Steuern aktiver Agenten. Ermöglicht Zeitsteuerung. |
| **CKU** | Compiled Knowledge Unit — kompilierte Darstellung eines Dokuments (noRAG-Format). |
| **TAIM Vault** | Dateisystem-basiertes Storage für Wissen, Memory und Konfiguration. |
| **Learning Loop** | Extrahiert Erkenntnisse nach jedem Prozess und überführt sie ins Memory. |
| **Approval Gate** | Punkt im Workflow der menschliche Bestätigung erfordert. |
| **Model Tier** | Klassifikation von LLMs nach Fähigkeit und Kosten für intelligente Zuweisung. |
| **Smart Default** | Intelligenter Vorgabewert den TAIM automatisch setzt und der User überschreiben kann. |
| **Intent Interpreter** | Übersetzt natürliche Sprache in strukturierte Aufträge für den Orchestrator. |
| **Ebene 1 / Ebene 2** | Conversation Layer (für jeden) vs. Configuration Layer (für Power-User). |

---

## Datenarchitektur: TAIM Vault

```
taim-vault/
│
├── config/                          # Globale Konfiguration
│   ├── taim.yaml                    # Hauptkonfiguration
│   ├── providers.yaml               # LLM-Provider
│   └── defaults.yaml                # Smart-Default-Werte
│
├── agents/                          # Agent-Definitionen
│   ├── code-reviewer.yaml
│   ├── frontend-dev.yaml
│   └── researcher.yaml
│
├── teams/                           # Team-Blueprints
│   ├── frontend-redesign.yaml
│   └── research-team.yaml
│
├── rules/                           # Compliance & Verhaltensregeln
│   ├── compliance/
│   │   ├── dsgvo.yaml
│   │   └── iso27001.yaml
│   ├── behavior/
│   │   └── engineering-standards.yaml
│   └── approvals/
│       └── default.yaml
│
├── shared/                          # Geteiltes Team-Wissen
│   ├── knowledge/                   # Compiled Knowledge (noRAG CKUs)
│   │   ├── .norag/                  # noRAG Store (SQLite Knowledge Map)
│   │   └── *.yaml                   # CKU-Dateien
│   ├── learning/                    # Team-weite Learning Loop Outputs
│   └── templates/                   # Wiederverwendbare Templates
│
├── users/                           # Pro User isoliert
│   ├── reyk/
│   │   ├── INDEX.md                 # Persönlicher Einstiegspunkt
│   │   ├── memory/                  # Persönliches Memory
│   │   ├── agents/                  # User-spezifische Agent-Overrides
│   │   └── history/                 # Auftrags-Historie
│   └── stefan/
│       └── ...
│
└── system/                          # TAIM-internes
    ├── learning/                    # System-weite Erkenntnisse
    ├── prompt-cache/                # Optimierte Prompts
    ├── audit/                       # Audit Trail (SQLite)
    └── state/                       # Session State (SQLite)
```

### Design-Prinzipien

- **Human-readable:** Alles Markdown oder YAML. Kein Binärformat.
- **Git-versionierbar:** Gesamter Vault kann in Git liegen.
- **Obsidian-kompatibel:** Wer lokal arbeitet, kann Teile als Obsidian-Vault öffnen — optional, nicht nötig.
- **SQLite für Performance:** Knowledge Map, Audit Trail, Session State. Markdown/YAML bleibt Source of Truth.

---

## Multi-User & Team-Betrieb

### User-Isolation

Jeder User hat eigenen Namespace (`users/{name}/`). Memory, Agent-Konfigurationen und Historie sind isoliert.

### Shared Knowledge

Team-weites Wissen liegt in `shared/`: Compiled Knowledge, Learning-Outputs, Templates. Für alle lesbar.

### RBAC

```yaml
roles:
  admin:
    can_edit: [rules/*, shared/*, config/*]
    can_manage: [users/*]
  team_lead:
    can_edit: [shared/knowledge/*, teams/*]
    can_view: [rules/*]
  member:
    can_edit: [users/{self}/*]
    can_view: [shared/*, teams/*, agents/*]
```

### Individualisierung

**Passiv:** Der Learning Loop schreibt Erkenntnisse in persönliches Memory. Über die Zeit entsteht ein präzises Profil.

**Aktiv:** Der User editiert sein Memory über Dashboard oder Conversation Layer. "Ich bevorzuge immer Tailwind CSS" → alle Agenten berücksichtigen das.

**Team-Lernen:** Gute Lösungen für wiederkehrende Probleme wandern in `shared/learning/`.

```
Learning Flow:
    ├── User-spezifisch?  → users/reyk/memory/
    ├── Team-relevant?    → shared/learning/
    └── System-relevant?  → system/prompt-cache/
```

---

## Deployment-Szenarien

### Szenario 1: Lokaler Einzelnutzer

```
Macbook / PC
├── TAIM Server (Python, lokal)
├── TAIM Dashboard (localhost:8080)
├── TAIM Vault (lokales Dateisystem)
├── LLMs: API-Keys + optional Ollama lokal
└── Optional: Obsidian als Vault-Viewer
```

### Szenario 2: Team-Server (gehostet)

```
AWS / On-Premise Server
├── TAIM Server (Docker)
├── TAIM Dashboard (Web, Port 443)
├── TAIM Vault (Persistent Volume)
├── PostgreSQL (State + Audit bei Last)
├── LLMs: API-Keys + optional AWS Bedrock
└── Reverse Proxy (Nginx/Caddy)
```

### Szenario 3: Enterprise

```
Kubernetes Cluster
├── TAIM Server (Replicas)
├── TAIM Dashboard (Load-balanced)
├── TAIM Vault (Shared Storage / EFS)
├── PostgreSQL (Managed / RDS)
├── LLMs: AWS Bedrock / Azure OpenAI / On-Prem Ollama
├── SSO (SAML/OIDC)
└── Monitoring (Prometheus/Grafana)
```

---

## Bestehende Bausteine

### noRAG (→ TAIM Brain, Schicht 1)

- **Repository:** https://github.com/reyk-zepper/noRAG
- **Status:** v1.0, Production-Ready
- **Liefert:** Knowledge Compiler, CKU-Format, SQLite Knowledge Map, REST API, Watch Mode, Audit Log, Benchmark Kit
- **Integration:** Python-Package in TAIM. noRAG CLI/API werden Teil des TAIM-Servers.
- **Lizenz:** Apache 2.0

### claudianX (→ TAIM Brain, Schicht 2)

- **Repository:** https://github.com/reyk-zepper/claudianX
- **Status:** Produktiv für Claude Code
- **Liefert:** Pattern für persistentes Memory: INDEX.md, Markdown-Notes, Frontmatter, JIT-Retrieval, Integrity-Checks
- **Integration:** Pattern wird generalisiert (Multi-User, Multi-Agent, ohne Obsidian) als TAIM Vault.
- **Lizenz:** MIT

### codian (→ TAIM Brain, Schicht 2)

- **Repository:** https://github.com/reyk-zepper/codian
- **Status:** Produktiv für Codex
- **Liefert:** Beweist Agent-Agnostik des claudianX-Patterns.
- **Integration:** Bestätigt Generalisierbarkeit. "Ein Vault pro Agent" wird "ein Namespace pro Agent".

---

## Tech Stack

| Komponente | Technologie | Begründung |
|-----------|-------------|------------|
| **Sprache** | Python 3.11+ | LLM-Ökosystem, noRAG-Kompatibilität |
| **API Server** | FastAPI + Uvicorn | Async, WebSocket, OpenAPI-Docs |
| **Dashboard** | React + TypeScript | Echtzeit-Updates, große Community |
| **Storage (Files)** | Dateisystem (Markdown/YAML) | Human-readable, git-versionierbar |
| **Storage (Index)** | SQLite + FTS5 | Zero-Config, Volltextsuche |
| **Storage (Scale)** | PostgreSQL (optional) | Für gehosteten Betrieb |
| **LLM Integration** | LiteLLM oder eigener Router | Unified API für 100+ Provider |
| **Knowledge Compiler** | noRAG | CKU-basiert, kein RAG |
| **CLI** | Typer + Rich | Typsicher, schöne Ausgabe |
| **Container** | Docker + docker-compose | Einfaches Deployment |
| **Enterprise** | Kubernetes Helm Chart | Skalierung + HA |

---

## Abgrenzung: Was TAIM nicht ist

- **Kein Expertentool.** TAIM ist für jeden. Technische Tiefe ist optional, nicht Voraussetzung.
- **Kein Ticket-System.** Tasks sind intern, der User interagiert per Conversation.
- **Kein Firmen-Simulator.** Keine Org-Charts, keine simulierte Unternehmensstruktur.
- **Kein No-Code-Workflow-Builder.** Kein Drag-and-Drop. Der Conversation Layer ist mächtiger und zugänglicher.
- **Kein Framework.** TAIM ist ein fertiges Produkt mit UI, nicht eine Library.
- **Kein Single-Agent-Tool.** TAIM ist für Teams. Einzelne Agenten → OpenClaw.
- **Kein Fine-Tuning-Tool.** TAIM optimiert Prompts und akkumuliert Erfahrungswissen.

---

## Phasenplan

### Phase 1 — Foundation (MVP)

**Ziel:** Die Kernschleife funktioniert: User beschreibt Aufgabe → TAIM stellt Team zusammen → Agenten arbeiten → Ergebnis wird geliefert.

**Umfang:**
- TAIM Server (FastAPI) mit REST API und WebSocket
- **Conversation Layer mit Intent Interpreter** (primäres Interface)
- **Guided Onboarding** (Einrichtung per Gespräch)
- **Smart Defaults** (User muss nichts konfigurieren)
- Agent Registry (YAML-basiert, aber via Conversation unsichtbar)
- Team Composer (Auto-Suggest basierend auf Aufgabe)
- TAIM Router mit Multi-LLM-Support und einfachem Failover
- TAIM Brain Schicht 2 (Agent Memory, claudianX-Pattern)
- Heartbeat Manager (Zeitlimit + Status-Check)
- Token-Tracking (pro Agent, pro Task)
- Dashboard mit integriertem Chat, Status-Ansicht, einfacher Stats-Seite
- CLI für Power-User (Ebene 2)

**Nicht in Phase 1:**
- noRAG-Integration (Compiled Knowledge)
- Learning Loop
- SWAT Builder
- Rules Engine
- Vollständiges Dashboard (Memory-Browser, Audit)
- Multi-User

### Phase 2 — Intelligence

**Ziel:** Das System lernt und wird durch Nutzung besser.

**Umfang:**
- TAIM Brain Schicht 1 (noRAG-Integration)
- TAIM Loop (Learning Loop + Prompt-Optimization)
- Few-Shot-Learning aus Memory
- Iteration Controller (automatisierte Review-Runden)
- SWAT Builder (automatisches Team-Spawning)
- Rules Engine (per Conversation oder YAML)
- Erweiterte Analytics im Dashboard

### Phase 3 — Scale

**Ziel:** Multi-User, Enterprise-Readiness, gehosteter Betrieb.

**Umfang:**
- Multi-User mit isoliertem Memory
- RBAC
- Vollständiges Dashboard (Memory-Browser, Audit Trail, Rules-Editor)
- Session State (Schicht 3 des Brain)
- Docker + docker-compose
- PostgreSQL-Support

### Phase 4 — Enterprise

**Ziel:** Produktionsreife für Unternehmenseinsatz.

**Umfang:**
- SSO (SAML/OIDC)
- Kubernetes Helm Chart
- AWS Bedrock / Azure OpenAI native Integration
- Automated Skill Discovery (MCP-Server)
- A2A-Protokoll-Support
- Compliance-Audit-Export

---

## Offene Entscheidungen

1. **LLM-Router: Eigenbau vs. LiteLLM?** LiteLLM bietet 100+ Provider out-of-the-box. Eigenbau gibt mehr Failover-Kontrolle. Kompromiss: LiteLLM als Transport, eigene Failover-Logik darüber.

2. **Dashboard-Framework:** React + Vite + TailwindCSS + Shadcn/ui als Basis?

3. **Agent-Execution-Model:** Subprocess? Docker Container? Direkter API-Call? Implikationen für Sandboxing.

4. **Kommunikation zwischen Agenten:** Shared State (SQLite)? Message Queue? Event Bus?

5. **Vault-Storage bei Scale:** Ab wann wird Dateisystem zum Bottleneck? Migration zu PostgreSQL parallel möglich?

6. **MCP-Integration:** TAIM als MCP-Server? Agenten als MCP-Clients?

7. **Intent Interpreter Modell:** Welches LLM für den Interpreter? Muss günstig und schnell sein (Tier 3?). Oder dediziertes kleines Modell?

8. **Conversation UX:** Wie detailliert erklärt TAIM seine Entscheidungen? Konfigurierbarer Detailgrad ("erkläre mir alles" vs. "mach einfach")?

9. **Offline-Fähigkeit:** Soll TAIM mit rein lokalen Modellen (Ollama) vollständig offline nutzbar sein?

---

## Validierung & Konsistenzprüfung

Die folgende Prüfung stellt sicher, dass das Dokument in sich schlüssig ist und als Grundlage für die Implementierung dienen kann.

### Architektur-Konsistenz

| Prüfpunkt | Status | Anmerkung |
|-----------|--------|-----------|
| Conversation Layer ist in Architekturdiagramm als primärer Eingang dargestellt | ✅ | Sitzt oben im Dashboard, über dem Orchestrator |
| Intent Interpreter verbindet Conversation Layer mit Orchestrator | ✅ | Eigene Schicht zwischen Dashboard und Orchestrator |
| Smart Defaults werden vom Memory gespeist | ✅ | Context Assembler + Agent Memory (Schicht 2) liefern Erfahrungswerte |
| Guided Onboarding generiert initiale Konfiguration | ✅ | Provider, Rules, User-Profil werden aus Gespräch abgeleitet |
| Ebene 1 und Ebene 2 greifen auf dieselbe Engine zu | ✅ | Conversation Layer und CLI/YAML steuern denselben Orchestrator |
| noRAG hat keine Obsidian-Abhängigkeit | ✅ | Eigenständig, Python, SQLite |
| claudianX-Pattern hat keine Obsidian-Abhängigkeit in TAIM | ✅ | Generalisiert als TAIM Vault, Obsidian nur optionaler Viewer |
| Rules Engine per Conversation und YAML zugänglich | ✅ | Beide Wege in Sektion 5 beschrieben |
| Learning Loop schreibt in korrekte Vault-Pfade | ✅ | users/{name}/memory, shared/learning, system/prompt-cache |
| Multi-User-Isolation gewährleistet | ✅ | users/{name}/ Namespace, RBAC definiert |

### Prinzipien-Konsistenz

| Prinzip | Durchgängig umgesetzt? | Anmerkung |
|---------|----------------------|-----------|
| Conversation First | ✅ | Jede Komponente hat Conversation-Zugang beschrieben |
| Progressive Disclosure | ✅ | Ebene 1/2 Muster durchgängig. Smart Defaults überall. |
| Control First | ✅ | Heartbeat, Approval Gates, Budget-Limits, Zeit-Limits |
| Learn by Use | ✅ | Learning Loop, Prompt-Optimization, Few-Shot, Memory |
| No Vendor Lock-in | ✅ | Router, Multi-Provider, Model Tiering |
| Compile Don't Search | ✅ | noRAG als Schicht 1, kein RAG nirgends |
| Transparency | ✅ | Markdown/YAML/SQLite, Audit Trail, Memory-Browser |
| Intelligent Scaling | ✅ | Team vs. SWAT vs. Einzelagent, Model Tiering |

### Phasenplan-Konsistenz

| Prüfpunkt | Status | Anmerkung |
|-----------|--------|-----------|
| Phase 1 enthält Conversation Layer | ✅ | Primäres Interface von Anfang an, nicht nachträglich |
| Phase 1 enthält Guided Onboarding | ✅ | Einrichtung per Gespräch statt Konfiguration |
| Phase 1 enthält Smart Defaults | ✅ | Kein User muss konfigurieren |
| Phase 1 CLI für Power-User | ✅ | Ebene 2 als Option, nicht als Hauptweg |
| noRAG (Schicht 1) erst in Phase 2 | ✅ | Sinnvoll — Memory (Schicht 2) reicht für MVP |
| Learning Loop erst in Phase 2 | ✅ | MVP sammelt Daten, Phase 2 lernt daraus |
| Multi-User erst in Phase 3 | ✅ | Lokaler Single-User für MVP ausreichend |
| Enterprise-Features in Phase 4 | ✅ | SSO, K8s, A2A sind klar Enterprise-Scope |

### Zielgruppen-Konsistenz

| Prüfpunkt | Status | Anmerkung |
|-----------|--------|-----------|
| Primäre Zielgruppe (jedermann) wird durch Conversation Layer bedient | ✅ | Kein technisches Wissen nötig |
| Sekundäre Zielgruppe (Power-User) wird durch Ebene 2 bedient | ✅ | YAML, CLI, API vollständig verfügbar |
| Tertiäre Zielgruppe (Enterprise) wird durch Phase 3+4 bedient | ✅ | Compliance, RBAC, SSO, Audit |
| Abgrenzung sagt "kein Expertentool" | ✅ | Konsistent mit AI-Equalizer-Vision |

### Identifizierte Spannungsfelder

**1. Conversation Layer Qualität ist kritischer Pfad.** Wenn der Intent Interpreter schlecht arbeitet, scheitert die gesamte Zugänglichkeits-Vision. Risiko-Mitigation: Ausreichend Konversations-Beispiele testen, Fallback auf explizite Rückfragen statt falsche Annahmen.

**2. Smart Defaults bei Erstnutzung.** Ohne Memory-Daten hat TAIM keine User-spezifischen Defaults. Risiko-Mitigation: Gute generische Defaults + Guided Onboarding liefern initiales Profil. Qualität steigt schnell mit Nutzung.

**3. Ebene-1/Ebene-2-Grenze.** Wenn ein Conversation-Befehl nicht reicht, muss der User wissen dass Ebene 2 existiert. Risiko-Mitigation: TAIM schlägt proaktiv vor: "Ich kann das Team auch manuell konfigurieren lassen — willst du die Details sehen?"

**4. Kosten-Transparenz.** Ein Anfänger versteht möglicherweise nicht, was "150k Tokens" bedeutet. Risiko-Mitigation: Immer in Euro/Dollar anzeigen, nie nur in Tokens. Token-Details nur in Stats-Ansicht.

---

## Lizenz & Philosophie

**Lizenz:** Apache 2.0

TAIM ist und bleibt Open Source. Keine Crippled-Free-Tier, keine proprietären Enterprise-Extensions. Der gesamte Kern ist frei verfügbar, modifizierbar und selbst hostbar.

**Warum Apache 2.0:**
- Erlaubt kommerzielle Nutzung und Redistribution
- Patent-Grant schützt Nutzer
- Kompatibel mit noRAGs bestehender Lizenz

**Philosophie:** Die Zukunft der Produktivität gehört nicht denen, die am besten prompten können. Sie gehört jedem, der Ideen hat und Ergebnisse will. TAIM macht den Unterschied zwischen "ich kenne AI" und "AI kennt mich" irrelevant.

---

> **TAIM — Team AI Manager**
> 
> *Weil die Zukunft der Produktivität nicht ein besserer Chatbot ist, sondern ein intelligentes Team das für dich arbeitet — egal wieviel du über KI weißt.*

---

*Dokument erstellt: 12. April 2026*
*Version: 2.0 — Überarbeitet mit AI-Equalizer-Vision, Conversation-First-Architektur, Validierung*
*Autoren: Reyk Zepper, Claude (Anthropic)*
*Status: Validiert — Grundlage für Implementierung*
