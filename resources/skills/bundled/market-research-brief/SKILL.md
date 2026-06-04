---
name: market-research-brief
description: Researches market trends, user needs, and competitive landscape using web search, API data, and documentation
category: research
version: 1.0.0
author: Construct
---

# Market Research Brief

## Overview

The **Market Research Brief** skill conducts comprehensive market analysis by synthesizing data from web searches, public APIs, industry reports, documentation, and social signals. It identifies market trends, quantifies addressable market size, maps the competitive landscape, and uncovers unmet user needs. The output is a structured research brief that informs product strategy, go-to-market planning, and investment decisions. This skill combines automated data collection with structured analytical frameworks.

## Checks Performed

- **Market Size Estimation**: TAM (Total Addressable Market), SAM (Serviceable Addressable Market), SOM (Serviceable Obtainable Market)
- **Trend Analysis**: Emerging technology trends, adoption curves, and market growth trajectories
- **User Needs Research**: Pain points, feature requests, satisfaction gaps from forums, reviews, and social media
- **Competitive Landscape**: Market share, positioning, strengths/weaknesses of key players
- **Pricing Intelligence**: Pricing models, tiers, and willingness-to-pay signals
- **Regulatory Environment**: Compliance requirements, upcoming legislation, and regulatory risks
- **Channel Analysis**: Distribution channels, partnership ecosystems, and go-to-market pathways
- **Technology Shifts**: Platform migrations, paradigm changes, and disruption indicators

## Execution Steps

1. **Define Research Scope**
   - Articulate the research question or hypothesis (e.g., "Is there demand for X in Y market?")
   - Define target industry, geography, user segments, and time horizon
   - Identify 5-10 relevant data sources and APIs
   - Set success criteria for the research brief

2. **Collect Secondary Data**
   - Search industry reports (Gartner, Forrester, IDC, Statista) for market sizing data
   - Query public datasets (World Bank, government statistics, census data)
   - Gather analyst predictions and venture capital investment trends
   - Compile relevant news articles, blog posts, and whitepapers from the last 24 months

3. **Analyze Web Signals**
   - Search Google Trends for keyword interest trajectories
   - Scrape Reddit, Hacker News, Stack Overflow, and specialized forums for user discussions
   - Analyze Twitter/X and LinkedIn sentiment and volume for relevant hashtags
   - Review App Store and Google Play ratings/reviews for competing products
   - Search GitHub for repository stars, forks, and issue activity in the problem domain

4. **Query Public APIs**
   - Fetch market data from financial APIs (Yahoo Finance, Alpha Vantage) for public competitors
   - Use Crunchbase API for startup funding and acquisition data
   - Query job posting APIs (LinkedIn, Indeed) to gauge hiring trends and skill demand
   - Pull web traffic estimates from SimilarWeb or SEMrush APIs

5. **Synthesize User Needs**
   - Extract and categorize pain points from forum discussions and reviews
   - Build a Jobs-to-be-Done (JTBD) framework for target users
   - Identify the top 10 most requested features or improvements
   - Map user satisfaction scores against competitor offerings
   - Validate needs with survey data if available

6. **Map Competitive Positioning**
   - Create a competitive matrix: features, pricing, market share, target segments
   - Plot competitors on a perceptual map (price vs. functionality, or other relevant axes)
   - Identify white-space opportunities (underserved segments or unmet needs)
   - Analyze competitor funding, partnerships, and strategic moves

7. **Forecast Market Trajectory**
   - Project market growth using CAGR from multiple analyst sources
   - Identify inflection points: technology shifts, regulatory changes, economic factors
   - Model best-case, base-case, and worst-case scenarios
   - Assess the window of opportunity for market entry

8. **Compile Research Brief**
   - Write executive summary with key findings and recommendations
   - Document methodology, data sources, and limitations
   - Include all charts, tables, and visualizations
   - Output: `market-research-brief.md` with appendices for raw data

## Examples

### Example 1: AI Code Assistant Market Research

**Input:**
```bash
/market-research-brief --topic "AI code assistants for enterprise developers" --geography global --timeframe 2024-2027
```

**Execution:**
```bash
# Web signals
google-trends --terms "github copilot","ai coding assistant","code completion ai" --time 2022-2024
reddit-scrape --subreddits r/programming,r/webdev,r/MachineLearning --query "AI coding assistant"
github-search --query "copilot alternative" --sort stars

# API queries
crunchbase-search --categories "developer-tools","AI" --funding 2023-2024
linkedin-jobs --keywords "AI engineer","LLM developer" --time 6m
```

**Output:**
```markdown
# Market Research Brief: AI Code Assistants for Enterprise

## Executive Summary

The AI code assistant market is experiencing explosive growth, expanding from
$1.2B (2023) to a projected $8.5B by 2027 at a 63% CAGR. Enterprise adoption
is the primary growth driver, with 72% of Fortune 500 companies piloting or
deploying AI coding tools in 2024.

## Market Size

| Metric | Value |
|--------|-------|
| TAM (2027) | $8.5B |
| SAM (Enterprise segment) | $4.2B |
| SOM (Realistic capture in 3 years) | $150M - $400M |

## Competitive Landscape

| Player | Market Share | Price/Developer/Mo | Enterprise Focus | Key Strength |
|--------|-------------|-------------------|-----------------|-------------|
| GitHub Copilot | ~45% | $19-39 | Yes | IDE integration, brand |
| Amazon CodeWhisperer | ~12% | $0-19 | Yes | AWS integration |
| JetBrains AI | ~8% | $10 | No | Deep IDE integration |
| Tabnine | ~7% | $12 | Yes | Privacy, on-prem |
| Cursor | ~5% | $20 | No | Fast, modern UX |
| Cody (Sourcegraph) | ~3% | $19 | Yes | Code intelligence |

## Key Trends

1. **Enterprise privacy demand**: 68% of enterprises require on-premise or VPC deployment
2. **Multi-model strategy**: Winners support GPT-4, Claude, and local models simultaneously
3. **Agentic coding**: Shift from completion to autonomous code generation and refactoring
4. **IDE fragmentation**: VS Code dominance (72%) but JetBrains (18%) and Neovim (5%) growing

## User Pain Points (from 12,000+ forum posts analyzed)

| Rank | Pain Point | Frequency | Severity |
|------|-----------|-----------|----------|
| 1 | Hallucinated/incorrect code suggestions | 34% | Critical |
| 2 | Slow response latency (>500ms) | 28% | High |
| 3 | Poor understanding of large codebases | 22% | High |
| 4 | Privacy concerns with code upload | 19% | Critical |
| 5 | Limited language/framework support | 15% | Medium |

## Recommendation

**ENTER NOW** — the market is in rapid growth phase with no clear winner in the
enterprise privacy-focused segment. A product combining local model support,
enterprise-grade audit trails, and sub-200ms latency could capture 5-8% SAM
within 3 years.
```

### Example 2: Regional Market Entry Analysis

**Input:**
```bash
/market-research-brief --topic "cloud cost optimization tools" --geography APAC --markets japan,singapore,australia,india
```

**Output:**
```json
{
  "brief": "cloud-cost-optimization-apac",
  "markets_analyzed": ["Japan", "Singapore", "Australia", "India"],
  "date": "2024-01-15",
  "findings": {
    "Japan": {
      "tam_usd": 420000000,
      "growth_rate": "18% CAGR",
      "key_insight": "Strong preference for domestic vendors; compliance with FISC standards required",
      "top_competitors": ["CloudHealth", "Kubecost", "local: Cloco"],
      "entry_difficulty": "high",
      "recommendation": "Partner with local SI (Systems Integrator) for market entry"
    },
    "Singapore": {
      "tam_usd": 180000000,
      "growth_rate": "28% CAGR",
      "key_insight": "Hub for ASEAN regional HQs — high English proficiency, pro-tech regulation",
      "top_competitors": ["CloudHealth", "Spot.io", "Flexera"],
      "entry_difficulty": "low",
      "recommendation": "Ideal launchpad for APAC; set up regional HQ here"
    },
    "Australia": {
      "tam_usd": 350000000,
      "growth_rate": "22% CAGR",
      "key_insight": "High AWS/GCP adoption; strong FinOps community; GDPR-like privacy laws",
      "top_competitors": ["CloudHealth", "Kubecost", "Apptio"],
      "entry_difficulty": "medium",
      "recommendation": "Direct entry viable; attend Sydney FinOps meetups"
    },
    "India": {
      "tam_usd": 280000000,
      "growth_rate": "35% CAGR",
      "key_insight": "Price-sensitive market; high startup density; strong Kubernetes adoption",
      "top_competitors": ["Open-source tools", "CloudHealth", "local: nOps"],
      "entry_difficulty": "medium",
      "recommendation": "Freemium model essential; partner with AWS/Azure India teams"
    }
  },
  "recommended_entry_sequence": ["Singapore", "Australia", "India", "Japan"],
  "total_apac_opportunity_usd": 1230000000
}
```

### Example 3: Emerging Technology Validation

**Input:**
```bash
/market-research-brief --topic "WebAssembly (WASM) in serverless edge computing" --depth deep --signals tech
```

**Output:**
```markdown
## Technology Trend Analysis: WASM in Serverless Edge

### Adoption Curve Position
```
Innovators ████████ (2019-2021)
Early Adopters ██████████████ (2022-2023)
Early Majority ▓▓▓▓▓▓▓▓░░░░░░ (2024-2025) ← CURRENT
Late Majority ░░░░░░░░░░░░░░░░ (2026-2028)
Laggards ░░░░░░░░░░░░░░░░ (2029+)
```

### Signal Strength Analysis

| Signal Source | Strength | Trend |
|--------------|----------|-------|
| GitHub stars (wasmtime, wasmer) | High | +340% YoY |
| HN mentions | High | +180% YoY |
| Job postings ("WASM") | Medium | +95% YoY |
| Cloud vendor announcements | High | AWS, Cloudflare, Fastly all launched WASM products |
| Startup funding | Medium | $180M in WASM startups in 2023 |
| Conference talks | High | WASM track at KubeCon doubled in size |

### Key Insight

WASM has crossed the chasm from early adopter to early majority in the
edge/serverless use case. Cloudflare Workers (V8 isolates + WASM) processes
>10% of all internet traffic, creating massive validation. However, the
*developer experience* remains the primary blocker — tooling, debugging, and
language support are still immature compared to containers.

### Opportunity Window

**12-18 months** to establish a developer tooling or platform play before
incumbent cloud providers fully commoditize the space.
```

## Validation Criteria

- [ ] Research question is clearly defined and answered in the executive summary
- [ ] Market size is quantified with TAM/SAM/SOM breakdown from 2+ credible sources
- [ ] At least 5 direct competitors are identified and profiled
- [ ] User needs are backed by data from primary or secondary sources (not assumptions)
- [ ] Trend analysis includes quantitative growth metrics (CAGR, YoY change)
- [ ] Data sources are cited with dates and methodology notes
- [ ] Geographic and segment-specific differences are documented
- [ ] Report includes actionable recommendations prioritized by confidence level
- [ ] Limitations and data gaps are transparently disclosed
- [ ] Output is suitable for stakeholder review and decision-making

## Best Practices

- Always triangulate market size estimates from **at least 3 independent sources**
- Separate **signal from noise** — distinguish temporary hype from structural trends
- Weight recent data higher than historical data in rapidly changing markets
- Include **contrarian perspectives** — actively seek evidence against your hypothesis
- Use **primary research** (surveys, interviews) to validate secondary data findings
- Document data sources and collection dates for reproducibility
- Visualize data with charts and matrices for stakeholder consumption
- Update research briefs **quarterly** for fast-moving markets, **annually** for stable ones
- Flag **regulatory risks** early — they can invalidate entire market opportunities
- Combine quantitative metrics with qualitative judgment for recommendations

## Tools Required

| Tool | Purpose |
|------|---------|
| `curl` / `wget` | Web data collection and API queries |
| Google Trends API | Keyword interest and trend analysis |
| Crunchbase API | Startup funding and acquisition data |
| Yahoo Finance / `stock_finance_data` | Public competitor financial metrics |
| Reddit/HN API | Community discussion and sentiment analysis |
| GitHub API | Open-source project activity metrics |
| SimilarWeb / SEMrush API | Web traffic and competitive intelligence |
| World Bank Open Data | Macroeconomic and demographic data |
| `jq` | JSON data processing and transformation |
| `matplotlib` / `pandas` | Data visualization and statistical analysis |

## Related Skills

- `competitor-analysis` — Deep competitive intelligence on specific companies
- `brand-name-forge` — Naming strategy based on market positioning
- `legal-risk-assessment` — Regulatory compliance analysis for target markets
